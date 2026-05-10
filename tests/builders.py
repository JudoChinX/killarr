"""Test data builders for killarr test fixtures."""

from typing import Any
from typing import Self

from killarr.clients.arr import ArrClient
from killarr.clients.arr import LidarrClient
from killarr.clients.arr import RadarrClient
from killarr.clients.arr import SonarrClient

DEFAULT_SETTINGS = {
    'batch_size': 10,
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

    def with_added(self, added: str) -> Self:
        """Set the added timestamp field."""
        self._data['added'] = added
        return self

    def with_id(self, queue_id: int) -> Self:
        """Set the queue record ID."""
        self._data['id'] = queue_id
        return self

    def with_status_messages(self, messages: list[str]) -> Self:
        """Set statusMessages with a single message group."""
        self._data['statusMessages'] = [{'messages': messages}]
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
            'added': '2024-01-01T00:00:00Z',
        }

    def with_movie_id(self, movie_id: int) -> Self:
        """Set the movieId field.

        Args:
            movie_id: The ID of the movie.

        Returns:
            The builder instance.
        """
        self._data['movieId'] = movie_id
        return self

    def with_tags(self, tag_ids: list[int]) -> Self:
        """Set root-level tags.

        Args:
            tag_ids: List of integer tag IDs.

        Returns:
            The builder instance.
        """
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
            'added': '2024-01-01T00:00:00Z',
        }

    def with_episode_id(self, episode_id: int) -> Self:
        """Set the episodeId field.

        Args:
            episode_id: The ID of the episode.

        Returns:
            The builder instance.
        """
        self._data['episodeId'] = episode_id
        return self

    def with_tags(self, tag_ids: list[int]) -> Self:
        """Set tags on the nested series dict.

        Args:
            tag_ids: List of integer tag IDs.

        Returns:
            The builder instance.
        """
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
            'added': '2024-01-01T00:00:00Z',
        }

    def with_album_id(self, album_id: int) -> Self:
        """Set the albumId field.

        Args:
            album_id: The ID of the album.

        Returns:
            The builder instance.
        """
        self._data['albumId'] = album_id
        return self

    def with_tags(self, tag_ids: list[int]) -> Self:
        """Set tags on the nested artist dict.

        Args:
            tag_ids: List of integer tag IDs.

        Returns:
            The builder instance.
        """
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
        """Instantiate and return the client.

        Returns:
            An instance of the configured ArrClient subclass.
        """
        return self._class(
            name=self._name,
            url=self._url,
            api_key=self._api_key,
            settings=self._settings,
        )

    def lidarr(self) -> 'ClientBuilder':
        """Use LidarrClient.

        Returns:
            The builder instance.
        """
        self._class = LidarrClient
        return self

    def radarr(self) -> 'ClientBuilder':
        """Use RadarrClient.

        Returns:
            The builder instance.
        """
        self._class = RadarrClient
        return self

    def sonarr(self) -> 'ClientBuilder':
        """Use SonarrClient.

        Returns:
            The builder instance.
        """
        self._class = SonarrClient
        return self

    def with_name(self, name: str) -> 'ClientBuilder':
        """Set the instance name.

        Args:
            name: Human-readable name for the instance.

        Returns:
            The builder instance.
        """
        self._name = name
        return self

    def with_settings(self, **settings: Any) -> 'ClientBuilder':
        """Override specific settings.

        Args:
            **settings: Arbitrary setting overrides.

        Returns:
            The builder instance.
        """
        self._settings.update(settings)
        return self
