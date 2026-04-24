"""Test data builders for killarr test fixtures."""

from typing import Any
from typing import Self

from killarr.clients.arr import ArrClient
from killarr.clients.arr import LidarrClient
from killarr.clients.arr import RadarrClient
from killarr.clients.arr import SonarrClient

DEFAULT_SETTINGS = {
    'batch_size': 10,
    'remove_from_client': True,
    'blocklist': True,
    'search_again': True,
    'stagger_interval_seconds': 0,
    'dry_run': False,
    'include_tags': [],
    'exclude_tags': [],
}


class _QueueRecordBuilder:
    """Base builder for queue record dicts."""

    _data: dict[str, Any]

    def build(self) -> dict[str, Any]:
        """Return a copy of the built record."""
        return self._data.copy()

    def ok(self) -> Self:
        """Set trackedDownloadStatus to ok (not stalled)."""
        self._data['trackedDownloadStatus'] = 'ok'
        return self

    def warning(self) -> Self:
        """Set trackedDownloadStatus to warning (stalled)."""
        self._data['trackedDownloadStatus'] = 'warning'
        return self

    def with_id(self, queue_id: int) -> Self:
        """Set the queue record ID."""
        self._data['id'] = queue_id
        return self

    def with_title(self, title: str) -> Self:
        """Set the download title."""
        self._data['title'] = title
        return self


class RadarrQueueBuilder(_QueueRecordBuilder):
    """Builder for Radarr queue record dicts."""

    def __init__(self) -> None:
        """Initialize with default stalled Radarr queue record."""
        self._data: dict[str, Any] = {
            'id': 1,
            'movieId': 10,
            'title': 'Test.Movie.2023.BluRay.mkv',
            'trackedDownloadStatus': 'warning',
            'tags': [],
        }

    def with_movie_id(self, movie_id: int) -> Self:
        """Set the movieId field."""
        self._data['movieId'] = movie_id
        return self

    def with_tags(self, tag_ids: list[int]) -> Self:
        """Set root-level tags."""
        self._data['tags'] = tag_ids
        return self


class SonarrQueueBuilder(_QueueRecordBuilder):
    """Builder for Sonarr queue record dicts."""

    def __init__(self) -> None:
        """Initialize with default stalled Sonarr queue record."""
        self._data: dict[str, Any] = {
            'id': 1,
            'episodeId': 20,
            'title': 'Show.S01E01.mkv',
            'trackedDownloadStatus': 'warning',
            'series': {'id': 10, 'title': 'Test Show', 'tags': []},
        }

    def with_episode_id(self, episode_id: int) -> Self:
        """Set the episodeId field."""
        self._data['episodeId'] = episode_id
        return self

    def with_tags(self, tag_ids: list[int]) -> Self:
        """Set tags on the nested series dict."""
        self._data['series']['tags'] = tag_ids
        return self


class LidarrQueueBuilder(_QueueRecordBuilder):
    """Builder for Lidarr queue record dicts."""

    def __init__(self) -> None:
        """Initialize with default stalled Lidarr queue record."""
        self._data: dict[str, Any] = {
            'id': 1,
            'albumId': 20,
            'title': 'Artist - Album (2023).zip',
            'trackedDownloadStatus': 'warning',
            'artist': {'id': 10, 'artistName': 'Test Artist', 'tags': []},
        }

    def with_album_id(self, album_id: int) -> Self:
        """Set the albumId field."""
        self._data['albumId'] = album_id
        return self

    def with_tags(self, tag_ids: list[int]) -> Self:
        """Set tags on the nested artist dict."""
        self._data['artist']['tags'] = tag_ids
        return self


class ClientBuilder:
    """Builder for ArrClient test instances."""

    def __init__(self, client_class: type[ArrClient] = RadarrClient) -> None:
        """Initialize with RadarrClient and default settings."""
        self._class = client_class
        self._name = 'test'
        self._url = 'http://test'
        self._api_key = 'testkey'
        self._settings: dict[str, Any] = dict(DEFAULT_SETTINGS)

    def build(self) -> ArrClient:
        """Instantiate and return the client."""
        return self._class(
            name=self._name,
            url=self._url,
            api_key=self._api_key,
            settings=self._settings,
        )

    def radarr(self) -> 'ClientBuilder':
        """Use RadarrClient."""
        self._class = RadarrClient
        return self

    def sonarr(self) -> 'ClientBuilder':
        """Use SonarrClient."""
        self._class = SonarrClient
        return self

    def lidarr(self) -> 'ClientBuilder':
        """Use LidarrClient."""
        self._class = LidarrClient
        return self

    def with_settings(self, **settings: Any) -> 'ClientBuilder':
        """Override specific settings."""
        self._settings.update(settings)
        return self

    def with_name(self, name: str) -> 'ClientBuilder':
        """Set the instance name."""
        self._name = name
        return self
