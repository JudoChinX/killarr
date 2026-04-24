"""*arr API clients: base class and app-specific subclasses for queue management."""

import logging
import time
from abc import ABC
from abc import abstractmethod
from typing import override

import requests

from killarr.classifier import classify

_LOGGER = logging.getLogger(__name__)

type QueueItem = tuple[int, int, str, str]  # (queue_id, media_id, title, action)


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
            weight: Unused by killarr but kept for interface parity with rangarr.
        """
        self.name = name
        self.url = url.rstrip('/')
        self.settings = settings
        self.weight = weight
        self.batch_size: int = settings.get('batch_size', 10)
        self.stagger_seconds: int = settings.get('stagger_interval_seconds', 5)
        self.dry_run: bool = settings.get('dry_run', False)
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

    def _is_tag_filtered_out(self, record: dict) -> bool:
        """Return True if this record should be skipped due to tag filtering rules."""
        record_tag_ids = set(self._get_record_tags(record))
        return bool(
            (self._exclude_tag_ids and record_tag_ids & self._exclude_tag_ids)
            or (self._include_tag_ids and not record_tag_ids & self._include_tag_ids)
        )

    def _remove_single(self, queue_id: int, media_id: int, title: str, action: str, index: int, total: int) -> None:
        """DELETE a single queue item and optionally trigger a fresh search."""
        if self.dry_run:
            _LOGGER.info(f'[{self.name}] [DRY RUN] Would {action}: {title} ({index}/{total})')
            return

        params: dict[str, str] = {'removeFromClient': 'true'}
        if action == 'blocklist':
            params['blocklist'] = 'true'

        url = f'{self.url}{self.ENDPOINT_QUEUE}/{queue_id}'
        try:
            response = self.session.delete(url, params=params, timeout=15)
            if response.status_code == 404:
                _LOGGER.info(f'[{self.name}] Removed ({action}, cascade): {title} ({index}/{total})')
            else:
                response.raise_for_status()
                _LOGGER.info(f'[{self.name}] Removed ({action}): {title} ({index}/{total})')
        except requests.RequestException as error:
            _LOGGER.error(f'[{self.name}] Failed to remove {title} (ID: {queue_id}): {error}')
            return

        if action in ('retry', 'blocklist'):
            self._trigger_search(media_id, title)

    def _resolve_action(self, category: str) -> str:
        """Resolve the action for a stall category using the config hierarchy."""
        return self.settings.get(category) or 'ignore'

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

    def get_stalled_items(self) -> list[QueueItem]:
        """Fetch the queue, classify each stalled item, and return those with a non-ignore action.

        Returns:
            List of (queue_id, media_id, title, action) tuples for actionable stalled items.
        """
        if self.batch_size == 0:
            return []

        all_records = self._fetch_all_queue()
        items: list[QueueItem] = []

        for record in all_records:
            if not self._is_stalled(record):
                continue

            messages: list[str] = []
            for msg_obj in record.get('statusMessages', []):
                messages.extend(msg_obj.get('messages', []))

            category = classify(messages)
            if category == 'unknown':
                title = self._get_record_title(record)
                _LOGGER.warning(
                    f'[{self.name}] Unrecognised status messages for "{title}" '
                    f'— please open a bug report at https://github.com/JudoChinX/killarr/issues '
                    f'with the following: {messages}'
                )
            action = self._resolve_action(category)

            if action == 'ignore':
                continue

            if self._is_tag_filtered_out(record):
                title = self._get_record_title(record)
                _LOGGER.debug(f'[{self.name}] Skipping stalled item (tag filter): {title}')
                continue

            queue_id = record['id']
            media_id = self._get_media_id(record)
            title = self._get_record_title(record)
            items.append((queue_id, media_id, title, action))

            if self.batch_size > 0 and len(items) >= self.batch_size:
                break

        return items

    def remove_stalled(self, items: list[QueueItem]) -> None:
        """Remove each stalled item from the queue, staggering between calls.

        Args:
            items: List of (queue_id, media_id, title, action) tuples.
        """
        total = len(items)
        for index, (queue_id, media_id, title, action) in enumerate(items, start=1):
            self._remove_single(queue_id, media_id, title, action, index, total)
            if self.stagger_seconds > 0 and index < total:
                _LOGGER.debug(f'[{self.name}] Staggering next removal by {self.stagger_seconds}s.')
                time.sleep(self.stagger_seconds)


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
