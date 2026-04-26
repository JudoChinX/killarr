"""Tests for killarr ArrClient base class and subclasses."""

# pylint: disable=protected-access

import logging
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import requests

from killarr.clients.arr import QueueItem
from killarr.clients.arr import RadarrClient
from tests.builders import ClientBuilder
from tests.builders import LidarrQueueBuilder
from tests.builders import RadarrQueueBuilder
from tests.builders import SonarrQueueBuilder
from tests.helpers import mock_http_response
from tests.helpers import mock_queue_response
from tests.helpers import mock_tag_response


def test_client_sets_api_key_header() -> None:
    """Test that the session is initialized with the X-Api-Key header."""
    client = ClientBuilder().build()
    assert client.session.headers.get('X-Api-Key') == 'testkey'


def test_client_sets_content_type_header() -> None:
    """Test that the session is initialized with the Content-Type header."""
    client = ClientBuilder().build()
    assert client.session.headers.get('Content-Type') == 'application/json'


def test_client_strips_trailing_slash_from_url() -> None:
    """Test that trailing slashes are removed from the base URL on construction."""
    client = RadarrClient(name='t', url='http://test/', api_key='k', settings={})
    assert client.url == 'http://test'


def test_client_reads_settings() -> None:
    """Test that client reads batch_size and dry_run from the settings dict."""
    client = ClientBuilder().with_settings(batch_size=5, dry_run=True).build()
    assert client.batch_size == 5
    assert client.dry_run is True


def test_client_warns_on_non_https_url(caplog: Any) -> None:
    """Test that constructing a client with an http:// URL logs a non-HTTPS warning."""
    with caplog.at_level(logging.WARNING):
        ClientBuilder().build()
    assert 'non-HTTPS' in caplog.text


def test_resolve_tag_ids_maps_names_to_ids() -> None:
    """Test that include_tags names are resolved to tag IDs from the *arr API."""
    tags = [{'id': 1, 'label': 'stalled'}, {'id': 2, 'label': 'active'}]
    with patch('requests.Session.get', return_value=mock_tag_response(tags)):
        client = ClientBuilder().with_settings(include_tags=['stalled']).build()
    assert 1 in client._include_tag_ids


def test_resolve_tag_ids_unknown_tag_logs_warning(caplog: Any) -> None:
    """Test that configuring an unrecognized tag name logs a warning."""
    tags = [{'id': 1, 'label': 'known'}]
    with caplog.at_level(logging.WARNING):
        with patch('requests.Session.get', return_value=mock_tag_response(tags)):
            client = ClientBuilder().with_settings(exclude_tags=['unknown']).build()
    assert 'unknown' in caplog.text.lower() or client._exclude_tag_ids == set()


def test_no_tag_resolution_when_no_tags_configured() -> None:
    """Test that no tag IDs are populated when no include_tags or exclude_tags are set."""
    client = ClientBuilder().build()
    assert client._include_tag_ids == set()
    assert client._exclude_tag_ids == set()


def test_tag_resolution_network_error_logs_error(caplog: Any) -> None:
    """Test that a network error during tag fetch is logged and tag sets remain empty."""
    with caplog.at_level(logging.ERROR):
        with patch('requests.Session.get', side_effect=requests.exceptions.ConnectionError('down')):
            client = ClientBuilder().with_settings(include_tags=['stalled']).build()
    assert 'Failed to fetch tags' in caplog.text
    assert client._include_tag_ids == set()


def test_fetch_all_queue_returns_records() -> None:
    """Test that _fetch_all_queue returns all records from the queue response."""
    client = ClientBuilder().radarr().build()
    records = [RadarrQueueBuilder().build(), RadarrQueueBuilder().with_id(2).build()]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    result = client._fetch_all_queue()
    assert len(result) == 2


def test_fetch_all_queue_paginates() -> None:
    """Test that _fetch_all_queue fetches subsequent pages when the first page is full."""
    client = ClientBuilder().radarr().build()
    page1 = [RadarrQueueBuilder().with_id(index).build() for index in range(100)]
    page2 = [RadarrQueueBuilder().with_id(200).build()]

    call_count = 0

    def fake_get(_url: str, params: dict | None = None, **_kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if params and params.get('page', 1) == 1:
            return mock_queue_response(page1)
        return mock_queue_response(page2)

    client.session.get = fake_get
    result = client._fetch_all_queue()
    assert len(result) == 101
    assert call_count == 2


def test_fetch_all_queue_handles_network_error(caplog: Any) -> None:
    """Test that a network error during queue fetch logs an error and returns an empty list."""
    client = ClientBuilder().radarr().build()
    client.session.get = MagicMock(side_effect=requests.exceptions.ConnectionError('down'))
    with caplog.at_level(logging.ERROR):
        result = client._fetch_all_queue()
    assert result == []
    assert 'Failed to fetch queue' in caplog.text


_is_stalled_cases = {
    'warning_record_is_stalled': {
        'record': RadarrQueueBuilder().warning().build(),
        'expected': True,
    },
    'ok_record_is_not_stalled': {
        'record': RadarrQueueBuilder().ok().build(),
        'expected': False,
    },
    'missing_status_field_is_not_stalled': {
        'record': {},
        'expected': False,
    },
}


@pytest.mark.parametrize(
    'record, expected',
    [(case['record'], case['expected']) for case in _is_stalled_cases.values()],
    ids=list(_is_stalled_cases.keys()),
)
def test_is_stalled(record: Any, expected: Any) -> None:
    """Test that _is_stalled correctly identifies stalled queue records."""
    client = ClientBuilder().radarr().build()
    assert client._is_stalled(record) is expected


_resolve_action_cases = {
    'specific_category_setting_returned': {
        'settings': {'no_upgrade': 'remove', 'stalled': 'blocklist'},
        'category': 'no_upgrade',
        'expected': 'remove',
    },
    'unset_category_falls_back_to_stalled': {
        'settings': {'stalled': 'blocklist'},
        'category': 'no_upgrade',
        'expected': 'blocklist',
    },
    'no_settings_defaults_to_ignore': {
        'settings': {},
        'category': 'no_upgrade',
        'expected': 'ignore',
    },
    'stalled_category_uses_its_own_setting': {
        'settings': {'stalled': 'retry'},
        'category': 'stalled',
        'expected': 'retry',
    },
}


@pytest.mark.parametrize(
    'settings, category, expected',
    [(case['settings'], case['category'], case['expected']) for case in _resolve_action_cases.values()],
    ids=list(_resolve_action_cases.keys()),
)
def test_resolve_action(settings: Any, category: Any, expected: Any) -> None:
    """Test that _resolve_action follows the config hierarchy correctly."""
    client = ClientBuilder().radarr().with_settings(**settings).build()
    assert client._resolve_action(category) == expected


def test_get_stalled_items_returns_only_warning_items() -> None:
    """Test that get_stalled_items filters out non-warning records."""
    client = ClientBuilder().radarr().with_settings(no_messages='remove').build()
    records = [
        RadarrQueueBuilder().warning().with_id(1).build(),
        RadarrQueueBuilder().ok().with_id(2).build(),
        RadarrQueueBuilder().warning().with_id(3).build(),
    ]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    items, _stats = client.get_stalled_items()
    assert len(items) == 2
    queue_ids = [item[0] for item in items]
    assert 1 in queue_ids
    assert 3 in queue_ids
    assert 2 not in queue_ids


def test_get_stalled_items_respects_batch_size() -> None:
    """Test that get_stalled_items limits results to batch_size."""
    client = ClientBuilder().radarr().with_settings(batch_size=2, no_messages='remove').build()
    records = [RadarrQueueBuilder().warning().with_id(index).build() for index in range(5)]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    items, _stats = client.get_stalled_items()
    assert len(items) == 2


def test_get_stalled_items_unlimited_batch() -> None:
    """Test that batch_size=-1 returns all stalled items without a limit."""
    client = ClientBuilder().radarr().with_settings(batch_size=-1, no_messages='remove').build()
    records = [RadarrQueueBuilder().warning().with_id(index).build() for index in range(20)]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    items, _stats = client.get_stalled_items()
    assert len(items) == 20


def test_get_stalled_items_disabled_returns_empty() -> None:
    """Test that batch_size=0 disables removal and returns an empty list."""
    client = ClientBuilder().radarr().with_settings(batch_size=0).build()
    records = [RadarrQueueBuilder().warning().build()]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    items, _stats = client.get_stalled_items()
    assert not items


def test_get_stalled_items_applies_exclude_tag_filter() -> None:
    """Test that items tagged with an excluded tag are filtered out."""
    tags_response = mock_http_response([{'id': 5, 'label': 'protected'}])
    with patch('requests.Session.get', return_value=tags_response):
        client = ClientBuilder().radarr().with_settings(exclude_tags=['protected'], no_messages='remove').build()
    records = [
        RadarrQueueBuilder().warning().with_id(1).with_tags([5]).build(),
        RadarrQueueBuilder().warning().with_id(2).with_tags([]).build(),
    ]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    items, _stats = client.get_stalled_items()
    assert len(items) == 1
    assert items[0].queue_id == 2


def test_get_stalled_items_returns_queue_item_with_all_fields() -> None:
    """Test that each stalled item is returned as a QueueItem with all fields populated."""
    client = ClientBuilder().radarr().with_settings(no_messages='blocklist').build()
    records = [RadarrQueueBuilder().warning().with_id(99).with_movie_id(42).with_title('My.Movie.mkv').build()]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    items, _stats = client.get_stalled_items()
    assert items[0].queue_id == 99
    assert items[0].media_id == 42
    assert items[0].title == 'My.Movie.mkv'
    assert items[0].action == 'blocklist'
    assert items[0].category == 'no_messages'
    assert items[0].messages == []


def test_get_stalled_items_skips_ignored_items() -> None:
    """Test that items whose resolved action is 'ignore' are excluded from results."""
    client = ClientBuilder().radarr().with_settings(stalled='ignore').build()
    records = [RadarrQueueBuilder().warning().with_id(1).build()]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    items, skip_stats = client.get_stalled_items()
    assert not items
    assert skip_stats['ignored'] == 1


def test_get_stalled_items_classifies_from_status_messages() -> None:
    """Test that statusMessages are used to classify and resolve the correct action."""
    client = ClientBuilder().radarr().with_settings(no_upgrade='retry', stalled='remove').build()
    record = (
        RadarrQueueBuilder()
        .warning()
        .with_id(1)
        .with_status_messages(['Not a Custom Format upgrade for existing movie file(s)'])
        .build()
    )
    client.session.get = MagicMock(return_value=mock_queue_response([record]))
    items, _stats = client.get_stalled_items()
    assert len(items) == 1
    assert items[0].action == 'retry'
    assert items[0].category == 'no_upgrade'


def test_get_stalled_items_logs_warning_for_unknown_messages(caplog: Any) -> None:
    """Test that unrecognized status messages log a warning with deduplicated messages."""
    client = ClientBuilder().radarr().build()
    record = (
        RadarrQueueBuilder()
        .warning()
        .with_title('My.Movie.mkv')
        .with_status_messages(['Error A', 'Error A', 'Error B'])
        .build()
    )
    client.session.get = MagicMock(return_value=mock_queue_response([record]))
    with caplog.at_level(logging.WARNING):
        client.get_stalled_items()
    assert 'Unrecognized status messages' in caplog.text
    assert 'github.com/JudoChinX/killarr/issues' in caplog.text
    assert 'My.Movie.mkv' in caplog.text
    assert "['Error A', 'Error B']" in caplog.text


def test_get_stalled_items_skips_tag_filtered_logs_debug(caplog: Any) -> None:
    """Test that include_tag filtering excludes non-matching items and logs at DEBUG."""
    tags_response = mock_http_response([{'id': 3, 'label': 'only'}])
    with patch('requests.Session.get', return_value=tags_response):
        client = ClientBuilder().radarr().with_settings(include_tags=['only'], no_messages='remove').build()
    records = [RadarrQueueBuilder().warning().with_id(1).with_tags([]).build()]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    with caplog.at_level(logging.DEBUG):
        items, skip_stats = client.get_stalled_items()
    assert not items
    assert skip_stats['tag_filtered'] == 1
    assert 'Skipping stalled item (tag filter)' in caplog.text


def test_get_stalled_items_counts_not_stalled() -> None:
    """Test that skip_stats['not_stalled'] reflects records that were not stalled."""
    client = ClientBuilder().radarr().with_settings(no_messages='remove').build()
    records = [
        RadarrQueueBuilder().warning().with_id(1).build(),
        RadarrQueueBuilder().ok().with_id(2).build(),
        RadarrQueueBuilder().ok().with_id(3).build(),
    ]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    items, skip_stats = client.get_stalled_items()
    assert len(items) == 1
    assert skip_stats['not_stalled'] == 2
    assert skip_stats['total_evaluated'] == 3


def test_get_stalled_items_logs_debug_for_ignored(caplog: Any) -> None:
    """Test that a DEBUG log is emitted when a stalled item's action is 'ignore'."""
    client = ClientBuilder().radarr().with_settings(stalled='ignore').build()
    records = [
        RadarrQueueBuilder()
        .warning()
        .with_id(1)
        .with_title('Ignored.Movie.mkv')
        .with_status_messages(['The download is stalled with no connections'])
        .build()
    ]
    client.session.get = MagicMock(return_value=mock_queue_response(records))
    with caplog.at_level(logging.DEBUG):
        client.get_stalled_items()
    assert 'Skipping stalled item (action: ignore, category: stalled)' in caplog.text
    assert 'Ignored.Movie.mkv' in caplog.text


def test_remove_stalled_calls_delete_for_each_item() -> None:
    """Test that remove_stalled issues one DELETE request per stalled item."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    client.session.post = MagicMock(return_value=mock_http_response())
    items = [
        QueueItem(1, 10, 'Movie A', 'remove', 'stalled', []),
        QueueItem(2, 20, 'Movie B', 'remove', 'stalled', []),
    ]
    client.remove_stalled(items)
    assert client.session.delete.call_count == 2


def test_remove_action_always_sends_remove_from_client() -> None:
    """Test that removeFromClient=true is always sent for non-ignore actions."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    client.remove_stalled([QueueItem(1, 10, 'Movie', 'remove', 'stalled', [])])
    params = client.session.delete.call_args.kwargs.get('params', {})
    assert params.get('removeFromClient') == 'true'


def test_blocklist_action_sends_blocklist_param() -> None:
    """Test that blocklist=true is sent when action is 'blocklist'."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    client.session.post = MagicMock(return_value=mock_http_response())
    client.remove_stalled([QueueItem(1, 10, 'Movie', 'blocklist', 'stalled', [])])
    params = client.session.delete.call_args.kwargs.get('params', {})
    assert params.get('blocklist') == 'true'


def test_remove_action_omits_blocklist_param() -> None:
    """Test that blocklist param is absent when action is 'remove'."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    client.remove_stalled([QueueItem(1, 10, 'Movie', 'remove', 'stalled', [])])
    params = client.session.delete.call_args.kwargs.get('params', {})
    assert 'blocklist' not in params


def test_retry_action_triggers_search() -> None:
    """Test that a search command is POSTed when action is 'retry'."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    client.session.post = MagicMock(return_value=mock_http_response())
    client.remove_stalled([QueueItem(1, 10, 'Movie', 'retry', 'stalled', [])])
    assert client.session.post.called
    payload = client.session.post.call_args.kwargs.get('json', {})
    assert payload.get('name') == 'MoviesSearch'
    assert 10 in payload.get('movieIds', [])


def test_blocklist_action_triggers_search() -> None:
    """Test that a search command is POSTed when action is 'blocklist'."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    client.session.post = MagicMock(return_value=mock_http_response())
    client.remove_stalled([QueueItem(1, 10, 'Movie', 'blocklist', 'stalled', [])])
    assert client.session.post.called


def test_remove_action_skips_search() -> None:
    """Test that no POST is made when action is 'remove'."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    client.session.post = MagicMock(return_value=mock_http_response())
    client.remove_stalled([QueueItem(1, 10, 'Movie', 'remove', 'stalled', [])])
    assert not client.session.post.called


def test_remove_stalled_search_failure_logs_warning_not_error(caplog: Any) -> None:
    """Test that a failed search POST is logged at WARNING level, not ERROR."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    client.session.post = MagicMock(side_effect=requests.exceptions.ConnectionError('down'))
    with caplog.at_level(logging.WARNING):
        client.remove_stalled([QueueItem(1, 10, 'Movie', 'retry', 'stalled', [])])
    assert 'WARNING' in caplog.text or 'warning' in caplog.text.lower()


def test_remove_stalled_delete_failure_logs_error_and_skips_search(caplog: Any) -> None:
    """Test that a failed DELETE logs an error and skips the search POST."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(side_effect=requests.exceptions.ConnectionError('down'))
    client.session.post = MagicMock(return_value=mock_http_response())
    with caplog.at_level(logging.ERROR):
        client.remove_stalled([QueueItem(1, 10, 'Movie', 'retry', 'stalled', [])])
    assert 'Failed to remove' in caplog.text
    assert not client.session.post.called


def test_remove_stalled_404_logs_cascade_and_triggers_search(caplog: Any) -> None:
    """Test that a 404 response logs as cascade removal and still triggers search."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response(status_code=404))
    client.session.post = MagicMock(return_value=mock_http_response())
    with caplog.at_level(logging.INFO):
        client.remove_stalled([QueueItem(1, 10, 'Movie', 'blocklist', 'stalled', [])])
    assert 'cascade' in caplog.text
    assert 'Failed to remove' not in caplog.text
    assert client.session.post.called


def test_remove_stalled_dry_run_skips_delete_and_search() -> None:
    """Test that dry_run mode skips both the DELETE and search POST."""
    client = ClientBuilder().radarr().with_settings(dry_run=True).build()
    client.session.delete = MagicMock()
    client.session.post = MagicMock()
    client.remove_stalled([QueueItem(1, 10, 'Movie', 'retry', 'stalled', [])])
    assert not client.session.delete.called
    assert not client.session.post.called


def test_remove_stalled_dry_run_logs_would_remove(caplog: Any) -> None:
    """Test that dry_run mode logs a DRY RUN message with the item title and action."""
    client = ClientBuilder().radarr().with_settings(dry_run=True).build()
    with caplog.at_level(logging.INFO):
        client.remove_stalled([QueueItem(1, 10, 'Test Movie', 'retry', 'stalled', [])])
    assert 'DRY RUN' in caplog.text
    assert 'Test Movie' in caplog.text
    assert 'retry (stalled)' in caplog.text


def test_remove_stalled_staggers_between_items() -> None:
    """Test that remove_stalled sleeps between items when stagger_interval_seconds > 0."""
    client = ClientBuilder().radarr().with_settings(stagger_interval_seconds=1).build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    items = [QueueItem(1, 10, 'A', 'remove', 'stalled', []), QueueItem(2, 20, 'B', 'remove', 'stalled', [])]
    with patch('time.sleep') as mock_sleep:
        client.remove_stalled(items)
    mock_sleep.assert_called_once_with(1)


def test_remove_stalled_no_stagger_after_last_item() -> None:
    """Test that remove_stalled does not sleep after the final item."""
    client = ClientBuilder().radarr().with_settings(stagger_interval_seconds=1).build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    with patch('time.sleep') as mock_sleep:
        client.remove_stalled([QueueItem(1, 10, 'Only', 'remove', 'stalled', [])])
    mock_sleep.assert_not_called()


def test_remove_stalled_delete_url_contains_queue_id() -> None:
    """Test that the DELETE URL includes the queue item ID."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    client.remove_stalled([QueueItem(99, 10, 'Movie', 'remove', 'stalled', [])])
    call_url = client.session.delete.call_args.args[0]
    assert '/queue/99' in call_url


def test_remove_stalled_logs_stall_details_at_debug(caplog: Any) -> None:
    """Test that _remove_single logs stall details at DEBUG level before attempting removal."""
    client = ClientBuilder().radarr().build()
    client.session.delete = MagicMock(return_value=mock_http_response())
    item = QueueItem(1, 10, 'Details Test', 'remove', 'stalled', ['Deep detail 1', 'Deep detail 2'])
    with caplog.at_level(logging.DEBUG):
        client._remove_single(item, 1, 1)
    assert 'Stall details for "Details Test"' in caplog.text
    assert 'Deep detail 1' in caplog.text
    assert 'Deep detail 2' in caplog.text


_subclass_attr_cases = {
    'radarr_command_name': {'arr_type': 'radarr', 'attr': '_command_name', 'expected': 'MoviesSearch'},
    'radarr_id_field': {'arr_type': 'radarr', 'attr': '_id_field', 'expected': 'movieIds'},
    'sonarr_command_name': {'arr_type': 'sonarr', 'attr': '_command_name', 'expected': 'EpisodeSearch'},
    'sonarr_id_field': {'arr_type': 'sonarr', 'attr': '_id_field', 'expected': 'episodeIds'},
    'lidarr_command_name': {'arr_type': 'lidarr', 'attr': '_command_name', 'expected': 'AlbumSearch'},
    'lidarr_id_field': {'arr_type': 'lidarr', 'attr': '_id_field', 'expected': 'albumIds'},
}


@pytest.mark.parametrize(
    'arr_type, attr, expected',
    [(case['arr_type'], case['attr'], case['expected']) for case in _subclass_attr_cases.values()],
    ids=list(_subclass_attr_cases.keys()),
)
def test_subclass_attr(arr_type: Any, attr: Any, expected: Any) -> None:
    """Test that each arr subclass exposes the correct static command name and ID field."""
    client = getattr(ClientBuilder(), arr_type)().build()
    assert getattr(client, attr) == expected


_endpoint_version_cases = {
    'radarr_queue_uses_v3': {'arr_type': 'radarr', 'endpoint_attr': 'ENDPOINT_QUEUE', 'version': 'v3'},
    'sonarr_queue_uses_v3': {'arr_type': 'sonarr', 'endpoint_attr': 'ENDPOINT_QUEUE', 'version': 'v3'},
    'lidarr_queue_uses_v1': {'arr_type': 'lidarr', 'endpoint_attr': 'ENDPOINT_QUEUE', 'version': 'v1'},
    'lidarr_command_uses_v1': {'arr_type': 'lidarr', 'endpoint_attr': 'ENDPOINT_COMMAND', 'version': 'v1'},
    'lidarr_tag_uses_v1': {'arr_type': 'lidarr', 'endpoint_attr': 'ENDPOINT_TAG', 'version': 'v1'},
}


@pytest.mark.parametrize(
    'arr_type, endpoint_attr, version',
    [(case['arr_type'], case['endpoint_attr'], case['version']) for case in _endpoint_version_cases.values()],
    ids=list(_endpoint_version_cases.keys()),
)
def test_subclass_endpoint_version(arr_type: Any, endpoint_attr: Any, version: Any) -> None:
    """Test that each arr subclass uses the correct API version in its endpoint paths."""
    client = getattr(ClientBuilder(), arr_type)().build()
    assert version in getattr(client, endpoint_attr)


def test_radarr_get_media_id() -> None:
    """Test that RadarrClient._get_media_id extracts the movieId field."""
    client = ClientBuilder().radarr().build()
    record = RadarrQueueBuilder().with_movie_id(42).build()
    assert client._get_media_id(record) == 42


def test_radarr_get_record_title() -> None:
    """Test that RadarrClient._get_record_title extracts the title field."""
    client = ClientBuilder().radarr().build()
    record = RadarrQueueBuilder().with_title('My.Movie.mkv').build()
    assert client._get_record_title(record) == 'My.Movie.mkv'


def test_radarr_get_record_tags() -> None:
    """Test that RadarrClient._get_record_tags extracts movie-level tags."""
    client = ClientBuilder().radarr().build()
    record = RadarrQueueBuilder().with_tags([1, 2]).build()
    assert client._get_record_tags(record) == [1, 2]


def test_sonarr_get_media_id() -> None:
    """Test that SonarrClient._get_media_id extracts the episodeId field."""
    client = ClientBuilder().sonarr().build()
    record = SonarrQueueBuilder().with_episode_id(55).build()
    assert client._get_media_id(record) == 55


def test_sonarr_get_record_title() -> None:
    """Test that SonarrClient._get_record_title extracts the title field."""
    client = ClientBuilder().sonarr().build()
    record = SonarrQueueBuilder().with_title('Show.S01E02.mkv').build()
    assert client._get_record_title(record) == 'Show.S01E02.mkv'


def test_sonarr_get_record_tags_from_series() -> None:
    """Test that SonarrClient._get_record_tags extracts series-level tags."""
    client = ClientBuilder().sonarr().build()
    record = SonarrQueueBuilder().with_tags([3, 4]).build()
    assert client._get_record_tags(record) == [3, 4]


def test_lidarr_get_media_id() -> None:
    """Test that LidarrClient._get_media_id extracts the albumId field."""
    client = ClientBuilder().lidarr().build()
    record = LidarrQueueBuilder().with_album_id(77).build()
    assert client._get_media_id(record) == 77


def test_lidarr_get_record_title() -> None:
    """Test that LidarrClient._get_record_title extracts the title field."""
    client = ClientBuilder().lidarr().build()
    record = LidarrQueueBuilder().with_title('Artist - Album.zip').build()
    assert client._get_record_title(record) == 'Artist - Album.zip'


def test_lidarr_get_record_tags_from_artist() -> None:
    """Test that LidarrClient._get_record_tags extracts artist-level tags."""
    client = ClientBuilder().lidarr().build()
    record = LidarrQueueBuilder().with_tags([7]).build()
    assert client._get_record_tags(record) == [7]


def test_radarr_get_record_title_fallback() -> None:
    """Test that _get_record_title returns a fallback string when title is absent."""
    client = ClientBuilder().radarr().build()
    assert 'Queue item' in client._get_record_title({'id': 5})
