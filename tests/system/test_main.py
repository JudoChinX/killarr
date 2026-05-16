"""Tests for killarr main module."""

# pylint: disable=protected-access
import datetime
import json
import logging
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from killarr.clients.arr import LidarrClient
from killarr.clients.arr import QueueItem
from killarr.clients.arr import RadarrClient
from killarr.clients.arr import SonarrClient
from killarr.config_parser import load_config
from killarr.main import _apply_removal_order
from killarr.main import _calculate_eta
from killarr.main import _fmt_action
from killarr.main import _format_cycle_info
from killarr.main import _get_setting
from killarr.main import _is_within_active_hours
from killarr.main import _run_removal_cycle
from killarr.main import _seconds_until_window_open
from killarr.main import build_arr_clients
from killarr.main import verify_arr_clients
from tests.helpers import mock_http_response

_FIXTURES_DIR = Path(__file__).parent.parent / 'fixtures'


def _load_fixture(arr_type: str, filename: str) -> dict:
    """Load a JSON fixture file from the fixtures directory."""
    return json.loads((_FIXTURES_DIR / arr_type / filename).read_text())


_calculate_eta_cases = {
    'no_stagger_returns_empty': {
        'item_count': 3,
        'stagger_seconds': 0,
        'expected': '',
    },
    'no_items_returns_empty': {
        'item_count': 0,
        'stagger_seconds': 5,
        'expected': '',
    },
    'with_stagger_and_items': {
        'item_count': 2,
        'stagger_seconds': 5,
        'expected': ', 1 every 5s, ETA: 0:00:10',
    },
}


@pytest.mark.parametrize(
    'item_count, stagger_seconds, expected',
    [(case['item_count'], case['stagger_seconds'], case['expected']) for case in _calculate_eta_cases.values()],
    ids=list(_calculate_eta_cases.keys()),
)
def test_calculate_eta(item_count: Any, stagger_seconds: Any, expected: Any) -> None:
    """Test that _calculate_eta returns the correct ETA string."""
    assert _calculate_eta(item_count, stagger_seconds) == expected


_fmt_action_cases = {
    'none_returns_ignore': {
        'value': None,
        'expected': 'ignore',
    },
    'empty_dict_returns_ignore': {
        'value': {},
        'expected': 'ignore',
    },
    'remove_only': {
        'value': {'remove': True},
        'expected': 'remove',
    },
    'remove_and_blocklist': {
        'value': {'remove': True, 'blocklist': True},
        'expected': 'remove+blocklist',
    },
    'remove_and_search': {
        'value': {'remove': True, 'search': True},
        'expected': 'remove+search',
    },
    'all_flags': {
        'value': {'remove': True, 'blocklist': True, 'search': True},
        'expected': 'remove+blocklist+search',
    },
}


@pytest.mark.parametrize(
    'value, expected',
    [(case['value'], case['expected']) for case in _fmt_action_cases.values()],
    ids=list(_fmt_action_cases.keys()),
)
def test_fmt_action(value: Any, expected: Any) -> None:
    """Test that _fmt_action returns the correct human-readable flag string."""
    assert _fmt_action(value) == expected


_format_cycle_info_cases = {
    'basic': {
        'client_name': 'Radarr',
        'item_count': 3,
        'skip_stats': {'total_evaluated': 10, 'ignored': 4, 'tag_filtered': 3},
        'expected': '[Radarr] Found 3 items to remove (Evaluated: 10, Skipped: 7).',
    },
    'includes_retry_interval_in_skipped': {
        'client_name': 'Sonarr',
        'item_count': 1,
        'skip_stats': {'total_evaluated': 5, 'ignored': 1, 'tag_filtered': 1, 'retry_interval': 1},
        'expected': '[Sonarr] Found 1 items to remove (Evaluated: 5, Skipped: 3).',
    },
}


@pytest.mark.parametrize(
    'client_name, item_count, skip_stats, expected',
    [
        (case['client_name'], case['item_count'], case['skip_stats'], case['expected'])
        for case in _format_cycle_info_cases.values()
    ],
    ids=list(_format_cycle_info_cases.keys()),
)
def test_format_cycle_info(client_name: Any, item_count: Any, skip_stats: Any, expected: Any) -> None:
    """Test that _format_cycle_info returns the correct formatted string."""
    assert _format_cycle_info(client_name, item_count, skip_stats) == expected


_get_setting_cases = {
    'returns_value_from_dict': {
        'settings': {'interval': 900},
        'key': 'interval',
        'expected': 900,
    },
    'falls_back_to_schema_default_interval': {
        'settings': {},
        'key': 'interval',
        'expected': 3600,
    },
    'returns_false_default_for_dry_run': {
        'settings': {},
        'key': 'dry_run',
        'expected': False,
    },
}


@pytest.mark.parametrize(
    'settings, key, expected',
    [(case['settings'], case['key'], case['expected']) for case in _get_setting_cases.values()],
    ids=list(_get_setting_cases.keys()),
)
def test_get_setting(settings: Any, key: Any, expected: Any) -> None:
    """Test that _get_setting returns the dict value or falls back to schema default."""
    assert _get_setting(settings, key) == expected


_is_within_active_hours_cases = {
    'inside_same_day': {
        'start': datetime.time(9, 0),
        'end': datetime.time(17, 0),
        'now': datetime.time(12, 0),
        'expected': True,
    },
    'outside_same_day_before': {
        'start': datetime.time(9, 0),
        'end': datetime.time(17, 0),
        'now': datetime.time(8, 0),
        'expected': False,
    },
    'outside_same_day_after': {
        'start': datetime.time(9, 0),
        'end': datetime.time(17, 0),
        'now': datetime.time(18, 0),
        'expected': False,
    },
    'at_start_boundary': {
        'start': datetime.time(9, 0),
        'end': datetime.time(17, 0),
        'now': datetime.time(9, 0),
        'expected': True,
    },
    'at_end_boundary_excluded': {
        'start': datetime.time(9, 0),
        'end': datetime.time(17, 0),
        'now': datetime.time(17, 0),
        'expected': False,
    },
    'inside_midnight_crossing_before_midnight': {
        'start': datetime.time(22, 0),
        'end': datetime.time(6, 0),
        'now': datetime.time(23, 0),
        'expected': True,
    },
    'inside_midnight_crossing_after_midnight': {
        'start': datetime.time(22, 0),
        'end': datetime.time(6, 0),
        'now': datetime.time(3, 0),
        'expected': True,
    },
    'outside_midnight_crossing_midday': {
        'start': datetime.time(22, 0),
        'end': datetime.time(6, 0),
        'now': datetime.time(12, 0),
        'expected': False,
    },
}


@pytest.mark.parametrize(
    'start, end, now, expected',
    [(case['start'], case['end'], case['now'], case['expected']) for case in _is_within_active_hours_cases.values()],
    ids=list(_is_within_active_hours_cases.keys()),
)
def test_is_within_active_hours(start: Any, end: Any, now: Any, expected: Any) -> None:
    """Test that _is_within_active_hours correctly identifies whether now is inside the window."""
    assert _is_within_active_hours(start, end, now) == expected


_seconds_until_window_open_cases = {
    'window_opens_later_today': {
        'start': datetime.time(22, 0),
        'now': datetime.time(20, 0),
        'expected_seconds': 7200,
    },
    'window_already_passed_rolls_to_tomorrow': {
        'start': datetime.time(22, 0),
        'now': datetime.time(23, 0),
        'expected_seconds': 82800,
    },
    'window_opens_at_midnight': {
        'start': datetime.time(0, 0),
        'now': datetime.time(12, 0),
        'expected_seconds': 43200,
    },
}


@pytest.mark.parametrize(
    'start, now, expected_seconds',
    [(case['start'], case['now'], case['expected_seconds']) for case in _seconds_until_window_open_cases.values()],
    ids=list(_seconds_until_window_open_cases.keys()),
)
def test_seconds_until_window_open(start: Any, now: Any, expected_seconds: Any) -> None:
    """Test that _seconds_until_window_open returns the correct number of seconds until the window opens."""
    assert _seconds_until_window_open(start, now, today=datetime.date(2026, 4, 23)) == expected_seconds


def _make_item(queue_id: int, added: str) -> QueueItem:
    """Build a minimal QueueItem with the given queue_id and added timestamp."""
    return QueueItem(
        queue_id=queue_id,
        media_id=queue_id,
        title=f'Item{queue_id}',
        remove=True,
        blocklist=False,
        search=False,
        category='generic',
        messages=[],
        added=added,
    )


_apply_removal_order_cases = {
    'api_order_is_noop': {
        'clients': [([_make_item(1, '2024-03-01T00:00:00Z'), _make_item(2, '2024-01-01T00:00:00Z')], [1, 2])],
        'order': 'api_order',
    },
    'age_ascending_sorts_oldest_first': {
        'clients': [([_make_item(1, '2024-03-01T00:00:00Z'), _make_item(2, '2024-01-01T00:00:00Z')], [2, 1])],
        'order': 'age_ascending',
    },
    'age_descending_sorts_newest_first': {
        'clients': [([_make_item(1, '2024-01-01T00:00:00Z'), _make_item(2, '2024-03-01T00:00:00Z')], [2, 1])],
        'order': 'age_descending',
    },
    'empty_added_sorts_gracefully': {
        'clients': [([_make_item(1, ''), _make_item(2, '2024-01-01T00:00:00Z')], [2, 1])],
        'order': 'age_ascending',
    },
    'multiple_clients_each_sorted_independently': {
        'clients': [
            ([_make_item(1, '2024-03-01T00:00:00Z'), _make_item(2, '2024-01-01T00:00:00Z')], [2, 1]),
            ([_make_item(3, '2024-06-01T00:00:00Z'), _make_item(4, '2024-02-01T00:00:00Z')], [4, 3]),
        ],
        'order': 'age_ascending',
    },
}


@pytest.mark.parametrize(
    'clients, order',
    [(case['clients'], case['order']) for case in _apply_removal_order_cases.values()],
    ids=list(_apply_removal_order_cases.keys()),
)
def test_apply_removal_order(clients: Any, order: Any) -> None:
    """Test that _apply_removal_order sorts client backlogs by the specified order."""
    mock_clients = [MagicMock() for _ in clients]
    backlogs = {mock_clients[idx]: list(items) for idx, (items, _) in enumerate(clients)}
    _apply_removal_order(backlogs, order)
    for idx, (_, expected_ids) in enumerate(clients):
        result_ids = [item.queue_id for item in backlogs[mock_clients[idx]]]
        assert result_ids == expected_ids


def test_run_removal_cycle_applies_removal_order_before_removal() -> None:
    """Test that _run_removal_cycle calls execute_removal in age_ascending order."""
    old_item = QueueItem(1, 1, 'Old', True, False, False, 'generic', [], '2024-01-01T00:00:00Z')
    new_item = QueueItem(2, 2, 'New', True, False, False, 'generic', [], '2024-06-01T00:00:00Z')
    client = _make_mock_client('R', stalled_items=[new_item, old_item])
    removal_calls: list[QueueItem] = []
    client.execute_removal.side_effect = lambda item, idx, total: removal_calls.append(item)
    _run_removal_cycle([client], {'removal_order': 'age_ascending', 'batch_size': -1})
    assert removal_calls[0].queue_id == 1
    assert removal_calls[1].queue_id == 2


def _make_run_config(active_hours: str = '') -> dict:
    """Build a minimal run config dict with the given active_hours setting."""
    return {
        'global_settings': {'interval': 10, 'active_hours': active_hours},
        'instances': {
            'radarr': [{'name': 'R', 'url': 'http://r', 'api_key': 'k', 'weight': 1.0}],
            'sonarr': [],
            'lidarr': [],
        },
    }


def test_run_loop_skips_cycle_outside_active_hours(caplog: Any) -> None:
    """Test that run() skips the removal cycle and sleeps when outside active hours."""
    from killarr.main import run

    queue_data = _load_fixture('radarr', 'queue.json')
    cycle_calls: list[int] = []

    def fake_sleep(_secs: float) -> None:
        raise KeyboardInterrupt

    with patch('killarr.main._load_config_from_paths', return_value=_make_run_config('22:00-06:00')):
        with patch('requests.Session.get', return_value=mock_http_response(queue_data)):
            with patch('killarr.main._run_removal_cycle', side_effect=lambda *a: cycle_calls.append(1)):
                with patch('time.sleep', side_effect=fake_sleep):
                    with caplog.at_level(logging.INFO):
                        with pytest.raises(KeyboardInterrupt):
                            run()

    assert not cycle_calls
    assert 'Outside active hours' in caplog.text


def test_run_loop_runs_cycle_inside_active_hours() -> None:
    """Test that run() executes the removal cycle when inside active hours."""
    from killarr.main import run

    queue_data = _load_fixture('radarr', 'queue.json')
    cycle_calls: list[int] = []

    def fake_sleep(_secs: float) -> None:
        raise KeyboardInterrupt

    with patch('killarr.main._load_config_from_paths', return_value=_make_run_config('09:00-17:00')):
        with patch('requests.Session.get', return_value=mock_http_response(queue_data)):
            with patch('killarr.main._run_removal_cycle', side_effect=lambda *a: cycle_calls.append(1)):
                with patch('time.sleep', side_effect=fake_sleep):
                    with pytest.raises(KeyboardInterrupt):
                        run()

    assert len(cycle_calls) == 1


def test_run_loop_no_active_hours_runs_cycle(caplog: Any) -> None:
    """Test that run() executes the removal cycle when active_hours is not configured."""
    from killarr.main import run

    queue_data = _load_fixture('radarr', 'queue.json')
    cycle_calls: list[int] = []

    def fake_sleep(_secs: float) -> None:
        raise KeyboardInterrupt

    with patch('killarr.main._load_config_from_paths', return_value=_make_run_config('')):
        with patch('requests.Session.get', return_value=mock_http_response(queue_data)):
            with patch('killarr.main._run_removal_cycle', side_effect=lambda *a: cycle_calls.append(1)):
                with patch('time.sleep', side_effect=fake_sleep):
                    with caplog.at_level(logging.INFO):
                        with pytest.raises(KeyboardInterrupt):
                            run()

    assert len(cycle_calls) == 1
    assert 'Outside active hours' not in caplog.text


def test_log_killarr_start_shows_active_hours(caplog: Any) -> None:
    """Test that _log_killarr_start logs the configured active_hours window."""
    from killarr.main import _log_killarr_start

    with caplog.at_level(logging.INFO):
        _log_killarr_start([MagicMock()], {'active_hours': '22:00-06:00'})
    assert 'Active Hours: 22:00-06:00' in caplog.text


def test_log_killarr_start_shows_all_hours_when_unset(caplog: Any) -> None:
    """Test that _log_killarr_start logs 'All hours' when active_hours is not set."""
    from killarr.main import _log_killarr_start

    with caplog.at_level(logging.INFO):
        _log_killarr_start([MagicMock()], {})
    assert 'Active Hours: All hours' in caplog.text


def _make_instances_config(
    arr_type: str = 'radarr',
    name: str = 'TestRadarr',
    url: str = 'http://r:7878',
    api_key: str = 'k',
    weight: float = 1.0,
) -> dict:
    """Build a minimal instances config dict for build_arr_clients."""
    return {arr_type: [{'name': name, 'url': url, 'api_key': api_key, 'weight': weight}]}


_build_arr_clients_cases = {
    'creates_radarr_client': {
        'instances': _make_instances_config('radarr'),
        'global_settings': {},
        'expected_count': 1,
        'expected_type': RadarrClient,
    },
    'creates_sonarr_client': {
        'instances': _make_instances_config('sonarr', url='http://s:8989'),
        'global_settings': {},
        'expected_count': 1,
        'expected_type': SonarrClient,
    },
    'creates_lidarr_client': {
        'instances': _make_instances_config('lidarr', url='http://l:8686'),
        'global_settings': {},
        'expected_count': 1,
        'expected_type': LidarrClient,
    },
}


@pytest.mark.parametrize(
    'instances, global_settings, expected_count, expected_type',
    [
        (case['instances'], case['global_settings'], case['expected_count'], case['expected_type'])
        for case in _build_arr_clients_cases.values()
    ],
    ids=list(_build_arr_clients_cases.keys()),
)
def test_build_arr_clients_type(instances: Any, global_settings: Any, expected_count: Any, expected_type: Any) -> None:
    """Test that build_arr_clients creates the correct client type for each arr instance."""
    clients = build_arr_clients(instances, global_settings)
    assert len(clients) == expected_count
    assert isinstance(clients[0], expected_type)


def test_build_arr_clients_sets_name() -> None:
    """Test that the client name is taken from the instance config."""
    clients = build_arr_clients(_make_instances_config(name='MyRadarr'), {})
    assert clients[0].name == 'MyRadarr'


def test_build_arr_clients_merges_instance_overrides() -> None:
    """Test that per-instance settings override global settings."""
    instances = {'radarr': [{'name': 'R', 'url': 'http://r', 'api_key': 'k', 'weight': 1.0, 'batch_size': 3}]}
    clients = build_arr_clients(instances, {'batch_size': 10})
    assert clients[0].batch_size == 3


def test_build_arr_clients_uses_global_settings_when_no_override() -> None:
    """Test that global settings are used when no per-instance override is present."""
    instances = {'radarr': [{'name': 'R', 'url': 'http://r', 'api_key': 'k', 'weight': 1.0}]}
    clients = build_arr_clients(instances, {'batch_size': 7})
    assert clients[0].batch_size == 7


def test_build_arr_clients_merges_instance_stall_category_overrides() -> None:
    """Test that per-instance stall category actions override global category settings."""
    instances = {
        'radarr': [
            {
                'name': 'R',
                'url': 'http://r',
                'api_key': 'k',
                'weight': 1.0,
                'no_upgrade': {'remove': True, 'search': True},
            }
        ]
    }
    clients = build_arr_clients(
        instances,
        {'no_upgrade': {'remove': False}, 'generic': {'remove': True}},
    )
    assert clients[0].settings['no_upgrade'] == {'remove': True, 'search': True}


def test_build_arr_clients_handles_multiple_types() -> None:
    """Test that build_arr_clients creates clients for all configured arr types."""
    instances = {
        'radarr': [{'name': 'R', 'url': 'http://r', 'api_key': 'k', 'weight': 1.0}],
        'sonarr': [{'name': 'S', 'url': 'http://s', 'api_key': 'k', 'weight': 1.0}],
        'lidarr': [],
    }
    clients = build_arr_clients(instances, {})
    assert len(clients) == 2


def test_build_arr_clients_returns_empty_for_empty_config() -> None:
    """Test that build_arr_clients returns an empty list when all instance lists are empty."""
    clients = build_arr_clients({'radarr': [], 'sonarr': [], 'lidarr': []}, {})
    assert not clients


def _make_mock_client(name: str = 'MockClient', stalled_items: list | None = None) -> MagicMock:
    """Create a mock ArrClient with get_stalled_items pre-configured."""
    client = MagicMock()
    client.name = name
    client.weight = 1.0
    actual_items = stalled_items or []
    stats = {
        'total_evaluated': len(actual_items),
        'ignored': 0,
        'tag_filtered': 0,
        'not_stalled': 0,
        'retry_interval': 0,
    }
    client.get_stalled_items.return_value = (actual_items, stats)
    return client


def test_run_removal_cycle_logs_no_stalled_when_empty(caplog: Any) -> None:
    """Test that _run_removal_cycle logs a 'No stalled items' message when the queue is clean."""
    client = _make_mock_client(name='Radarr', stalled_items=[])
    with caplog.at_level(logging.INFO):
        _run_removal_cycle([client], {})
    assert 'No stalled items' in caplog.text
    assert '(Evaluated: 0)' in caplog.text


def test_run_removal_cycle_logs_found_items_with_summary(caplog: Any) -> None:
    """Test that _run_removal_cycle logs cycle info when items are found."""
    client = _make_mock_client(name='Radarr', stalled_items=[(1, 10, 'Movie')])
    with caplog.at_level(logging.INFO):
        _run_removal_cycle([client], {})
    assert 'Found 1 items to remove' in caplog.text
    assert 'Evaluated:' in caplog.text


def test_run_removal_cycle_calls_get_stalled_for_each_client() -> None:
    """Test that _run_removal_cycle calls get_stalled_items on every client."""
    clients = [_make_mock_client('R'), _make_mock_client('S')]
    _run_removal_cycle(clients, {})
    for client in clients:
        client.get_stalled_items.assert_called_once()


def test_run_removal_cycle_calls_execute_removal_for_each_allocated_item() -> None:
    """Test that execute_removal is called once per allocated item."""
    item = QueueItem(1, 10, 'Movie', True, False, False, 'no_messages', [])
    client = _make_mock_client('R', stalled_items=[item])
    _run_removal_cycle([client], {'no_messages': {'remove': True}, 'batch_size': 10})
    client.execute_removal.assert_called_once_with(item, 1, 1)


def test_run_removal_cycle_skips_execute_when_no_items() -> None:
    """Test that execute_removal is never called when no stalled items exist."""
    client = _make_mock_client('R', stalled_items=[])
    _run_removal_cycle([client], {})
    client.execute_removal.assert_not_called()


def test_run_removal_cycle_respects_global_batch_size() -> None:
    """Test that batch_size caps total removals across all clients."""
    items = [QueueItem(i, i, f'M{i}', True, False, False, 'no_messages', []) for i in range(1, 6)]
    client = _make_mock_client('R', stalled_items=items)
    _run_removal_cycle([client], {'batch_size': 2})
    assert client.execute_removal.call_count == 2


def test_run_removal_cycle_batch_size_zero_skips_execution() -> None:
    """Test that batch_size=0 skips execute_removal even when items are present."""
    item = QueueItem(1, 10, 'Movie', True, False, False, 'no_messages', [])
    client = _make_mock_client('R', stalled_items=[item])
    _run_removal_cycle([client], {'batch_size': 0})
    client.execute_removal.assert_not_called()


def test_run_removal_cycle_interleave_true_alternates_clients() -> None:
    """Test that interleave_instances=True alternates items between clients."""
    item_a = QueueItem(1, 1, 'A', True, False, False, 'no_messages', [])
    item_b = QueueItem(2, 2, 'B', True, False, False, 'no_messages', [])
    client_a = _make_mock_client('CA', stalled_items=[item_a])
    client_b = _make_mock_client('CB', stalled_items=[item_b])
    client_a.weight = 1.0
    client_b.weight = 1.0
    _run_removal_cycle([client_a, client_b], {'interleave_instances': True, 'batch_size': -1})
    client_a.execute_removal.assert_called_once()
    client_b.execute_removal.assert_called_once()


def test_run_removal_cycle_interleave_false_drains_per_client() -> None:
    """Test that interleave_instances=False runs one client's items before the next."""
    calls = []
    item_a1 = QueueItem(1, 1, 'A1', True, False, False, 'no_messages', [])
    item_a2 = QueueItem(2, 2, 'A2', True, False, False, 'no_messages', [])
    item_b1 = QueueItem(3, 3, 'B1', True, False, False, 'no_messages', [])
    client_a = _make_mock_client('CA', stalled_items=[item_a1, item_a2])
    client_b = _make_mock_client('CB', stalled_items=[item_b1])
    client_a.weight = 1.0
    client_b.weight = 1.0
    client_a.execute_removal.side_effect = lambda item, index, total: calls.append(('CA', item))
    client_b.execute_removal.side_effect = lambda item, index, total: calls.append(('CB', item))
    _run_removal_cycle([client_a, client_b], {'interleave_instances': False, 'batch_size': -1})
    assert calls[0][0] == 'CA'
    assert calls[1][0] == 'CA'
    assert calls[2][0] == 'CB'


def test_run_exits_when_no_config() -> None:
    """Test that run() exits with code 1 when no config file can be loaded."""
    with patch('killarr.main._load_config_from_paths', return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            from killarr.main import run

            run()
    assert exc_info.value.code == 1


def test_run_exits_when_no_active_clients() -> None:
    """Test that run() exits with code 1 when all instance lists are empty."""
    config = {
        'global_settings': {},
        'instances': {'radarr': [], 'sonarr': [], 'lidarr': []},
    }
    with patch('killarr.main._load_config_from_paths', return_value=config):
        with pytest.raises(SystemExit) as exc_info:
            from killarr.main import run

            run()
    assert exc_info.value.code == 1


def test_load_config_from_paths_loads_existing_file(tmp_path: Any) -> None:
    """Test that _load_config_from_paths parses a valid config file."""
    from killarr.main import _load_config_from_paths

    cfg = tmp_path / 'config.yaml'
    cfg.write_text('instances:\n  r:\n    type: radarr\n    host: http://r\n    api_key: k\n    enabled: true\n')
    result = _load_config_from_paths([str(cfg)])
    assert result is not None
    assert 'global_settings' in result


def test_load_config_from_paths_returns_none_when_no_files(tmp_path: Any) -> None:
    """Test that _load_config_from_paths returns None when no paths exist."""
    from killarr.main import _load_config_from_paths

    result = _load_config_from_paths([str(tmp_path / 'nonexistent.yaml')])
    assert result is None


def test_load_config_from_paths_returns_none_on_value_error(tmp_path: Any) -> None:
    """Test that _load_config_from_paths returns None when the config fails validation."""
    from killarr.main import _load_config_from_paths

    cfg = tmp_path / 'bad.yaml'
    cfg.write_text('killarr:\n  interval: 60\n')
    result = _load_config_from_paths([str(cfg)])
    assert result is None


def test_load_config_from_paths_skips_missing_tries_next(tmp_path: Any) -> None:
    """Test that _load_config_from_paths skips missing files and loads the next valid one."""
    from killarr.main import _load_config_from_paths

    good = tmp_path / 'config.yaml'
    good.write_text('instances:\n  r:\n    type: radarr\n    host: http://r\n    api_key: k\n    enabled: true\n')
    result = _load_config_from_paths([str(tmp_path / 'missing.yaml'), str(good)])
    assert result is not None


def test_log_killarr_start_logs_instance_count(caplog: Any) -> None:
    """Test that _log_killarr_start logs the number of active instances."""
    from killarr.main import _log_killarr_start

    clients = [MagicMock(), MagicMock()]
    with caplog.at_level(logging.INFO):
        _log_killarr_start(clients, {})
    assert '2 active' in caplog.text


def test_log_killarr_start_shows_dry_run(caplog: Any) -> None:
    """Test that _log_killarr_start logs DRY RUN when dry_run is True."""
    from killarr.main import _log_killarr_start

    with caplog.at_level(logging.INFO):
        _log_killarr_start([MagicMock()], {'dry_run': True})
    assert 'DRY RUN' in caplog.text


def test_log_killarr_start_shows_disabled_batch(caplog: Any) -> None:
    """Test that _log_killarr_start logs 'Disabled' when batch_size is 0."""
    from killarr.main import _log_killarr_start

    with caplog.at_level(logging.INFO):
        _log_killarr_start([MagicMock()], {'batch_size': 0})
    assert 'Disabled' in caplog.text


def test_log_killarr_start_shows_unlimited_batch(caplog: Any) -> None:
    """Test that _log_killarr_start logs 'Unlimited' when batch_size is -1."""
    from killarr.main import _log_killarr_start

    with caplog.at_level(logging.INFO):
        _log_killarr_start([MagicMock()], {'batch_size': -1})
    assert 'Unlimited' in caplog.text


def test_log_killarr_start_shows_handling_actions(caplog: Any) -> None:
    """Test that _log_killarr_start logs stall category actions in flag format."""
    from killarr.main import _log_killarr_start

    with caplog.at_level(logging.INFO):
        _log_killarr_start([MagicMock()], {'generic': {'remove': True}})
    assert 'Handling:' in caplog.text
    assert 'generic=remove' in caplog.text


def test_log_killarr_start_empty_dict_results_in_ignore(caplog: Any) -> None:
    """Test that an explicit empty dict in config results in 'ignore' in the startup log."""
    from killarr.main import _log_killarr_start

    settings = {
        'generic': {'remove': True, 'blocklist': True, 'search': True},
        'no_upgrade': {},
    }
    with caplog.at_level(logging.INFO):
        _log_killarr_start([MagicMock()], settings)
    assert 'no_upgrade=ignore' in caplog.text
    assert 'generic=remove+blocklist+search' in caplog.text


def test_log_killarr_start_unset_category_falls_back_to_generic(caplog: Any) -> None:
    """Test that a category missing from config falls back to 'generic' actions in the log."""
    from killarr.main import _log_killarr_start

    settings = {
        'generic': {'remove': True, 'search': True},
        # manual_import is intentionally missing
    }
    with caplog.at_level(logging.INFO):
        _log_killarr_start([MagicMock()], settings)
    assert 'manual_import=remove+search' in caplog.text
    assert 'generic=remove+search' in caplog.text


def test_log_killarr_start_shows_interleave_yes(caplog: Any) -> None:
    """Test that the startup banner includes Interleave: Yes when interleave_instances is True."""
    from killarr.main import _log_killarr_start

    client = MagicMock()
    client.name = 'Radarr'
    settings = {'interleave_instances': True}
    with caplog.at_level(logging.INFO):
        _log_killarr_start([client], settings)
    assert 'Interleave: Yes' in caplog.text


def test_log_killarr_start_shows_interleave_no(caplog: Any) -> None:
    """Test that the startup banner includes Interleave: No when interleave_instances is False."""
    from killarr.main import _log_killarr_start

    client = MagicMock()
    client.name = 'Radarr'
    settings = {'interleave_instances': False}
    with caplog.at_level(logging.INFO):
        _log_killarr_start([client], settings)
    assert 'Interleave: No' in caplog.text


def test_run_env_source_loads_from_env(monkeypatch: Any) -> None:
    """Test that run() uses env-var config when KILLARR_CONFIG_SOURCE=env."""
    monkeypatch.setenv('KILLARR_CONFIG_SOURCE', 'env')
    monkeypatch.setenv('KILLARR_INSTANCE_0_NAME', 'R')
    monkeypatch.setenv('KILLARR_INSTANCE_0_TYPE', 'radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_URL', 'http://r')
    monkeypatch.setenv('KILLARR_INSTANCE_0_API_KEY', 'k')
    from killarr.main import run

    call_count = 0

    def fake_sleep(_interval: float) -> None:
        nonlocal call_count
        call_count += 1
        raise KeyboardInterrupt

    queue_data = _load_fixture('radarr', 'queue.json')
    with patch('requests.Session.get', return_value=mock_http_response(queue_data)):
        with patch('time.sleep', side_effect=fake_sleep):
            with pytest.raises(KeyboardInterrupt):
                run()
    assert call_count == 1


def test_run_env_source_exits_on_value_error(monkeypatch: Any) -> None:
    """Test that run() exits with code 1 when env-var config raises a ValueError."""
    monkeypatch.setenv('KILLARR_CONFIG_SOURCE', 'env')
    from killarr.main import run

    with patch('killarr.main.load_config_from_env', side_effect=ValueError('bad')):
        with pytest.raises(SystemExit) as exc_info:
            run()
    assert exc_info.value.code == 1


def test_run_unrecognized_source_warns(monkeypatch: Any, caplog: Any) -> None:
    """Test that run() logs a warning and exits when KILLARR_CONFIG_SOURCE is unrecognized."""
    monkeypatch.setenv('KILLARR_CONFIG_SOURCE', 'database')
    from killarr.main import run

    with patch('killarr.main._load_config_from_paths', return_value=None):
        with caplog.at_level(logging.WARNING):
            with pytest.raises(SystemExit):
                run()
    assert 'Unrecognized' in caplog.text


def test_run_loop_executes_cycle_and_sleeps(monkeypatch: Any) -> None:
    """Test that run() executes a removal cycle and sleeps for the configured interval."""
    monkeypatch.delenv('KILLARR_CONFIG_SOURCE', raising=False)
    config = {
        'global_settings': {'interval': 10},
        'instances': {
            'radarr': [{'name': 'R', 'url': 'http://r', 'api_key': 'k', 'weight': 1.0}],
            'sonarr': [],
            'lidarr': [],
        },
    }
    from killarr.main import run

    sleep_calls: list[float] = []

    def fake_sleep(interval: float) -> None:
        sleep_calls.append(interval)
        raise KeyboardInterrupt

    queue_data = _load_fixture('radarr', 'queue.json')
    with patch('killarr.main._load_config_from_paths', return_value=config):
        with patch('requests.Session.get', return_value=mock_http_response(queue_data)):
            with patch('time.sleep', side_effect=fake_sleep):
                with pytest.raises(KeyboardInterrupt):
                    run()
    assert sleep_calls == [10]


def test_load_config_with_expanded_types(tmp_path: Any, monkeypatch: Any) -> None:
    """Test that load_config correctly expands and types environment variables in YAML."""
    monkeypatch.setenv('TEST_INTERVAL', '900')
    monkeypatch.setenv('TEST_DRY_RUN', 'true')

    cfg = tmp_path / 'config.yaml'
    cfg.write_text(
        textwrap.dedent("""
        killarr:
          interval: ${TEST_INTERVAL}
          dry_run: ${TEST_DRY_RUN}
        instances:
          radarr:
            type: radarr
            host: "http://r"
            api_key: "k"
            enabled: true
    """)
    )

    result = load_config(str(cfg))
    assert result['global_settings']['interval'] == 900
    assert result['global_settings']['dry_run'] is True


def _make_mock_connection_client(name: str, side_effect: Any) -> MagicMock:
    """Build a mock arr client with a configurable check_connection side_effect."""
    client = MagicMock()
    client.name = name
    client.check_connection.side_effect = side_effect
    return client


_verify_arr_clients_cases = {
    'returns_all_when_all_connect': {
        'side_effects': [[True], [True]],
        'expected_count': 2,
    },
    'drops_client_that_never_connects': {
        'side_effects': [[True], [False, False, False]],
        'expected_count': 1,
    },
    'returns_empty_when_all_fail': {
        'side_effects': [[False, False, False], [False, False, False]],
        'expected_count': 0,
    },
}


@pytest.mark.parametrize(
    'side_effects, expected_count',
    [(case['side_effects'], case['expected_count']) for case in _verify_arr_clients_cases.values()],
    ids=list(_verify_arr_clients_cases.keys()),
)
def test_verify_arr_clients(side_effects: Any, expected_count: Any) -> None:
    """Test that verify_arr_clients returns only clients that connected successfully."""
    clients = [_make_mock_connection_client(f'Client{idx}', effects) for idx, effects in enumerate(side_effects)]
    result = verify_arr_clients(clients)
    assert len(result) == expected_count


def test_verify_arr_clients_retries_then_succeeds(caplog: Any) -> None:
    """Test that a client connecting on attempt 2 is included and logs 'attempt 2/3'."""
    client = _make_mock_connection_client('ClientA', [False, True])
    with caplog.at_level(logging.INFO):
        result = verify_arr_clients([client])
    assert len(result) == 1
    assert 'attempt 2/3' in caplog.text


def test_verify_arr_clients_logs_warning_on_retry(caplog: Any) -> None:
    """Test that a WARNING containing 'Retrying in' is logged when a connection attempt fails."""
    client = _make_mock_connection_client('ClientA', [False, True])
    with caplog.at_level(logging.WARNING):
        verify_arr_clients([client])
    assert 'Retrying in' in caplog.text


def test_verify_arr_clients_logs_error_on_exhaustion(caplog: Any) -> None:
    """Test that an ERROR containing 'Could not connect after' is logged when all attempts fail."""
    client = _make_mock_connection_client('ClientA', [False, False, False])
    with caplog.at_level(logging.ERROR):
        verify_arr_clients([client])
    assert 'Could not connect after' in caplog.text


def test_run_exits_when_all_verification_fails() -> None:
    """Test that run() exits with code 1 when verify_arr_clients returns an empty list."""
    config = {
        'global_settings': {},
        'instances': {
            'radarr': [{'name': 'R', 'url': 'http://r', 'api_key': 'k', 'weight': 1.0}],
            'sonarr': [],
            'lidarr': [],
        },
    }
    with patch('killarr.main._load_config_from_paths', return_value=config):
        with patch('killarr.main.verify_arr_clients', return_value=[]):
            with pytest.raises(SystemExit) as exc_info:
                from killarr.main import run

                run()
    assert exc_info.value.code == 1


def test_run_removal_cycle_staggers_between_items(monkeypatch: Any) -> None:
    """Test that _run_removal_cycle sleeps stagger_interval_seconds between items."""
    sleep_calls: list[float] = []
    monkeypatch.setattr('killarr.main.time.sleep', sleep_calls.append)
    items = [QueueItem(i, i, f'M{i}', True, False, False, 'no_messages', []) for i in range(1, 3)]
    client = _make_mock_client('R', stalled_items=items)
    _run_removal_cycle([client], {'stagger_interval_seconds': 5, 'batch_size': -1})
    assert sleep_calls == [5]  # one sleep between 2 items, none after last


def test_run_removal_cycle_no_sleep_after_last_item(monkeypatch: Any) -> None:
    """Test that _run_removal_cycle does not sleep after the final item."""
    sleep_calls: list[float] = []
    monkeypatch.setattr('killarr.main.time.sleep', sleep_calls.append)
    item = QueueItem(1, 1, 'M1', True, False, False, 'no_messages', [])
    client = _make_mock_client('R', stalled_items=[item])
    _run_removal_cycle([client], {'stagger_interval_seconds': 5, 'batch_size': -1})
    assert not sleep_calls  # only one item, no sleep
