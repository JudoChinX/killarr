"""*arr API clients: base class and app-specific subclasses for queue management."""

import datetime
import logging
from abc import ABC
from abc import abstractmethod
from typing import NamedTuple
from typing import override

import requests

from killarr.classifier import classify
from killarr.validators import VALID_ACTIONS

_LOGGER = logging.getLogger(__name__)


class QueueItem(NamedTuple):
    """Represents a single stalled queue item to be acted upon."""

    queue_id: int
    media_id: int
    title: str
    remove: bool
    blocklist: bool
    search: bool
    category: str
    messages: list[str]
    added: str = ''


class ArrClient(ABC):
    """Abstract base class for *arr queue management clients."""

    ENDPOINT_QUEUE = '/api/v3/queue'
    ENDPOINT_COMMAND = '/api/v3/command'
    ENDPOINT_TAG = '/api/v3/tag'

    def __init__(
        self,
        name: str,
        url: str,
        api_key: str,
        settings: dict,
        weight: float = 1.0,
    ) -> None:
        """Initialize the base *arr client.

        Args:
            name: Human-readable name for this instance.
            url: Base URL of the *arr service API.
            api_key: API key for authentication.
            settings: Merged configuration settings dict.
            weight: Priority multiplier for weighted round-robin slot allocation. Higher values receive proportionally more removal slots per cycle.
        """
        self.name = name
        self.url = url.rstrip('/')
        self.settings = settings
        self.weight = weight
        self.batch_size: int = settings.get('batch_size', 10)
        self.retry_interval_minutes: int = settings.get('retry_interval_minutes', 0)
        self.stagger_seconds: int = settings.get('stagger_interval_seconds', 5)
        self.dry_run: bool = settings.get('dry_run', False)
        self._retry_state: dict[int, datetime.datetime] = {}
        if not self.url.lower().startswith('https://'):
            _LOGGER.warning(
                f"Client '{name}' is using a non-HTTPS URL ({self.url}). API keys will be transmitted in plaintext."
            )
        self.session = requests.Session()
        self.session.headers.update({'X-Api-Key': api_key, 'Content-Type': 'application/json'})
        self._include_tag_ids: set[int] = set()
        self._exclude_tag_ids: set[int] = set()
        self._resolve_tag_ids()

    @property
    @abstractmethod
    def _command_name(self) -> str:
        """Return the API command name for a fresh search (e.g. 'MoviesSearch')."""

    def _fetch_all_queue(self) -> list[dict]:
        """Fetch all queue records across all pages."""
        result: list[dict] = []
        current_page = 1
        page_size = 100

        while True:
            url = f'{self.url}{self.ENDPOINT_QUEUE}'
            params = {'page': current_page, 'pageSize': page_size}
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                records = response.json().get('records', [])
                result.extend(records)
                if len(records) < page_size:
                    break
                current_page += 1
            except requests.RequestException as error:
                _LOGGER.error(f'[{self.name}] Failed to fetch queue: {error}')
                break

        return result

    @abstractmethod
    def _get_media_id(self, record: dict) -> int:
        """Extract the media item ID from a queue record for a follow-up search."""

    @abstractmethod
    def _get_record_tags(self, record: dict) -> list[int]:
        """Return the tag ID list from a queue record."""

    @abstractmethod
    def _get_record_title(self, record: dict) -> str:
        """Extract a human-readable title from a queue record."""

    @property
    @abstractmethod
    def _id_field(self) -> str:
        """Return the payload ID field name for a search command (e.g. 'movieIds')."""

    def _is_stalled(self, record: dict) -> bool:
        """Return True if the record is considered stalled by the arr app."""
        return record.get('trackedDownloadStatus') == 'warning'

    def _is_within_retry_interval(self, media_id: int) -> bool:
        """Return True if this media ID was actioned within the retry interval window."""
        recorded = self._retry_state.get(media_id)
        if self.retry_interval_minutes == 0 or recorded is None:
            return False
        cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=self.retry_interval_minutes)
        if recorded <= cutoff:
            del self._retry_state[media_id]
        return recorded > cutoff

    def _is_tag_filtered_out(self, record: dict) -> bool:
        """Return True if this record should be skipped due to tag filtering rules."""
        record_tag_ids = set(self._get_record_tags(record))
        return bool(
            (self._exclude_tag_ids and record_tag_ids & self._exclude_tag_ids)
            or (self._include_tag_ids and not record_tag_ids & self._include_tag_ids)
        )

    def _record_retry_interval(self, media_id: int, title: str) -> None:
        """Record the current time as the last-actioned timestamp for this media ID."""
        if self.retry_interval_minutes == 0:
            return
        self._retry_state[media_id] = datetime.datetime.now(datetime.UTC)
        _LOGGER.debug(f'[{self.name}] Cooldown recorded for media ID {media_id}: {title}')

    def _remove_single(self, item: QueueItem, index: int, total: int) -> None:
        """DELETE a single queue item and optionally trigger a fresh search."""
        _LOGGER.debug(f'[{self.name}] Stall details for "{item.title}": {item.messages}')
        parts = ['remove']
        if item.blocklist:
            parts.append('blocklist')
        if item.search:
            parts.append('search')
        action_label = '+'.join(parts)

        if self.dry_run:
            _LOGGER.info(
                f'[{self.name}] [DRY RUN] Would {action_label} ({item.category}): {item.title} ({index}/{total})'
            )
            return

        params: dict[str, str] = {'removeFromClient': 'true'}
        if item.blocklist:
            params['blocklist'] = 'true'

        url = f'{self.url}{self.ENDPOINT_QUEUE}/{item.queue_id}'
        try:
            response = self.session.delete(url, params=params, timeout=15)
            if response.status_code == 404:
                _LOGGER.info(
                    f'[{self.name}] Removed ({action_label}, {item.category}, cascade): {item.title} ({index}/{total})'
                )
                self._record_retry_interval(item.media_id, item.title)
            else:
                response.raise_for_status()
                _LOGGER.info(f'[{self.name}] Removed ({action_label}, {item.category}): {item.title} ({index}/{total})')
                self._record_retry_interval(item.media_id, item.title)
        except requests.RequestException as error:
            _LOGGER.error(f'[{self.name}] Failed to remove {item.title} (ID: {item.queue_id}): {error}')
            return

        if item.search:
            self._trigger_search(item.media_id, item.title)

    def _resolve_action(self, category: str) -> dict[str, bool]:
        """Resolve the action flags for a stall category using the config hierarchy."""
        action = self.settings.get(category)
        if action is None and category != 'stalled':
            action = self.settings.get('stalled')
        if action is None:
            action = {}
        return {key: action.get(key, False) for key in VALID_ACTIONS}

    def _resolve_tag_ids(self) -> None:
        """Fetch instance tags and resolve configured tag names to IDs."""
        include_names: list[str] = self.settings.get('include_tags', [])
        exclude_names: list[str] = self.settings.get('exclude_tags', [])
        if include_names or exclude_names:
            url = f'{self.url}{self.ENDPOINT_TAG}'
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                tag_map = {tag['label'].lower(): tag['id'] for tag in response.json()}
                self._include_tag_ids = self._resolve_tag_names(tag_map, include_names)
                self._exclude_tag_ids = self._resolve_tag_names(tag_map, exclude_names)
            except requests.RequestException as err:
                _LOGGER.error(f'[{self.name}] Failed to fetch tags, tag filtering disabled: {err}')

    def _resolve_tag_names(self, tag_map: dict[str, int], names: list[str]) -> set[int]:
        """Resolve tag name strings to integer IDs, warning on unknown names."""
        result: set[int] = set()
        for name in names:
            tag_id = tag_map.get(name.lower())
            if tag_id is None:
                _LOGGER.warning(f'[{self.name}] Tag not found, ignoring: {name}')
            else:
                result.add(tag_id)
        return result

    def _trigger_search(self, media_id: int, title: str) -> None:
        """POST a fresh search command for the given media item."""
        url = f'{self.url}{self.ENDPOINT_COMMAND}'
        payload = {'name': self._command_name, self._id_field: [media_id]}
        try:
            response = self.session.post(url, json=payload, timeout=15)
            response.raise_for_status()
            _LOGGER.debug(f'[{self.name}] Triggered search for: {title}')
        except requests.RequestException as error:
            _LOGGER.warning(f'[{self.name}] Failed to trigger search for {title} (ID: {media_id}): {error}')

    def check_connection(self) -> bool:
        """Return True if the instance tag endpoint responds successfully.

        Returns:
            True if the HTTP request succeeds, False on any network error.
        """
        url = f'{self.url}{self.ENDPOINT_TAG}'
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def get_stalled_items(self) -> tuple[list[QueueItem], dict[str, int]]:
        """Fetch the queue, classify each stalled item, and return actionable items and skip stats.

        Returns:
            Tuple of (list of QueueItem, dict of skip reasons).
        """
        if self.batch_size == 0:
            return [], {
                'total_evaluated': 0,
                'ignored': 0,
                'tag_filtered': 0,
                'not_stalled': 0,
                'retry_interval': 0,
            }

        all_records = self._fetch_all_queue()
        items: list[QueueItem] = []
        skip_stats: dict[str, int] = {
            'total_evaluated': len(all_records),
            'ignored': 0,
            'tag_filtered': 0,
            'not_stalled': 0,
            'retry_interval': 0,
        }

        for record in all_records:
            title = self._get_record_title(record)
            if not self._is_stalled(record):
                skip_stats['not_stalled'] += 1
                continue

            messages: list[str] = list(
                dict.fromkeys(
                    msg for msg_obj in record.get('statusMessages', []) for msg in msg_obj.get('messages', [])
                )
            )

            category = classify(messages)
            if category == 'unknown':
                _LOGGER.warning(
                    f'[{self.name}] Unrecognized status messages for "{title}" '
                    f'— please open a bug report at https://github.com/JudoChinX/killarr/issues '
                    f'with the following: {messages}'
                )
            action = self._resolve_action(category)

            if not action['remove']:
                _LOGGER.debug(f'[{self.name}] Skipping stalled item (remove=false, category: {category}): {title}')
                skip_stats['ignored'] += 1
                continue

            media_id = self._get_media_id(record)
            if self._is_within_retry_interval(media_id):
                _LOGGER.debug(f'[{self.name}] Skipping stalled item (retry_interval, media ID {media_id}): {title}')
                skip_stats['retry_interval'] += 1
                continue

            if self._is_tag_filtered_out(record):
                _LOGGER.debug(f'[{self.name}] Skipping stalled item (tag filter): {title}')
                skip_stats['tag_filtered'] += 1
                continue

            queue_id = record['id']
            added = record.get('added', '')
            items.append(
                QueueItem(
                    queue_id,
                    media_id,
                    title,
                    action['remove'],
                    action['blocklist'],
                    action['search'],
                    category,
                    messages,
                    added,
                )
            )

            if self.batch_size > 0 and len(items) >= self.batch_size:
                break

        return items, skip_stats

    def execute_removal(self, item: QueueItem, index: int, total: int) -> None:
        """Remove a single queue item.

        Args:
            item: The QueueItem to remove.
            index: 1-based position in the global removal queue.
            total: Total items in the global removal queue.
        """
        self._remove_single(item, index, total)


class LidarrClient(ArrClient):
    """Lidarr queue management client."""

    ENDPOINT_QUEUE = '/api/v1/queue'
    ENDPOINT_COMMAND = '/api/v1/command'
    ENDPOINT_TAG = '/api/v1/tag'

    @property
    @override
    def _command_name(self) -> str:
        return 'AlbumSearch'

    @override
    def _get_media_id(self, record: dict) -> int:
        return record['albumId']

    @override
    def _get_record_tags(self, record: dict) -> list[int]:
        return record.get('artist', {}).get('tags', [])

    @override
    def _get_record_title(self, record: dict) -> str:
        return record.get('title', f'Queue item {record.get("id", "Unknown")}')

    @property
    @override
    def _id_field(self) -> str:
        return 'albumIds'


class RadarrClient(ArrClient):
    """Radarr queue management client."""

    @property
    @override
    def _command_name(self) -> str:
        return 'MoviesSearch'

    @override
    def _get_media_id(self, record: dict) -> int:
        return record['movieId']

    @override
    def _get_record_tags(self, record: dict) -> list[int]:
        return record.get('tags', [])

    @override
    def _get_record_title(self, record: dict) -> str:
        return record.get('title', f'Queue item {record.get("id", "Unknown")}')

    @property
    @override
    def _id_field(self) -> str:
        return 'movieIds'


class SonarrClient(ArrClient):
    """Sonarr queue management client."""

    @property
    @override
    def _command_name(self) -> str:
        return 'EpisodeSearch'

    @override
    def _get_media_id(self, record: dict) -> int:
        return record['episodeId']

    @override
    def _get_record_tags(self, record: dict) -> list[int]:
        return record.get('series', {}).get('tags', [])

    @override
    def _get_record_title(self, record: dict) -> str:
        return record.get('title', f'Queue item {record.get("id", "Unknown")}')

    @property
    @override
    def _id_field(self) -> str:
        return 'episodeIds'
