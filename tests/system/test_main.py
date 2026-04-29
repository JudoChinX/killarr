"""Tests for killarr main module."""

import json
import logging
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from killarr.clients.arr import LidarrClient
from killarr.clients.arr import RadarrClient
from killarr.clients.arr import SonarrClient
from killarr.config_parser import load_config
from killarr.main import _calculate_eta
from killarr.main import _format_cycle_info
from killarr.main import _get_setting
from killarr.main import _run_removal_cycle
from killarr.main import build_arr_clients
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


_format_cycle_info_cases = {
    'basic_no_stagger': {
        'client_name': 'Radarr',
        'item_count': 3,
        'skip_stats': {'total_evaluated': 10, 'ignored': 4, 'tag_filtered': 3},
        'stagger_seconds': 0,
        'expected': '[Radarr] Found 3 items to remove (Evaluated: 10, Skipped: 7).',
    },
    'with_stagger_eta': {
        'client_name': 'Radarr',
        'item_count': 2,
        'skip_stats': {'total_evaluated': 10, 'ignored': 4, 'tag_filtered': 3},
        'stagger_seconds': 5,
        'expected': '[Radarr] Found 2 items to remove (Evaluated: 10, Skipped: 7, 1 every 5s, ETA: 0:00:10).',
    },
}


@pytest.mark.parametrize(
    'client_name, item_count, skip_stats, stagger_seconds, expected',
    [
        (case['client_name'], case['item_count'], case['skip_stats'], case['stagger_seconds'], case['expected'])
        for case in _format_cycle_info_cases.values()
    ],
    ids=list(_format_cycle_info_cases.keys()),
)
def test_format_cycle_info(
    client_name: Any, item_count: Any, skip_stats: Any, stagger_seconds: Any, expected: Any
) -> None:
    """Test that _format_cycle_info returns the correct formatted string."""
    assert _format_cycle_info(client_name, item_count, skip_stats, stagger_seconds) == expected


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
    instances = {'radarr': [{'name': 'R', 'url': 'http://r', 'api_key': 'k', 'weight': 1.0, 'no_upgrade': 'retry'}]}
    clients = build_arr_clients(instances, {'no_upgrade': 'ignore', 'stalled': 'remove'})
    assert clients[0].settings['no_upgrade'] == 'retry'


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


def _make_mock_client(name: str = 'TestClient', stalled_items: list | None = None) -> MagicMock:
    """Build a mock arr client with a configurable get_stalled_items return value."""
    client = MagicMock()
    client.name = name
    client.stagger_seconds = 0
    actual_items = stalled_items or []
    stats = {'total_evaluated': len(actual_items), 'ignored': 0, 'tag_filtered': 0, 'not_stalled': 0}
    client.get_stalled_items.return_value = (actual_items, stats)
    return client


_run_removal_cycle_cases = {
    'calls_get_stalled_for_each_client': {
        'clients': [_make_mock_client('R'), _make_mock_client('S')],
        'stalled_items': None,
        'expect_remove_called': False,
        'expect_stalled_call_count': 2,
    },
    'calls_remove_when_items_found': {
        'clients': [_make_mock_client(stalled_items=[(1, 10, 'Movie')])],
        'stalled_items': [(1, 10, 'Movie')],
        'expect_remove_called': True,
        'expect_stalled_call_count': 1,
    },
    'skips_remove_when_no_items': {
        'clients': [_make_mock_client(stalled_items=[])],
        'stalled_items': [],
        'expect_remove_called': False,
        'expect_stalled_call_count': 1,
    },
}


@pytest.mark.parametrize(
    'clients, stalled_items, expect_remove_called, expect_stalled_call_count',
    [
        (
            case['clients'],
            case['stalled_items'],
            case['expect_remove_called'],
            case['expect_stalled_call_count'],
        )
        for case in _run_removal_cycle_cases.values()
    ],
    ids=list(_run_removal_cycle_cases.keys()),
)
def test_run_removal_cycle(
    clients: Any,
    stalled_items: Any,
    expect_remove_called: Any,
    expect_stalled_call_count: Any,
) -> None:
    """Test that _run_removal_cycle polls each client and removes stalled items as expected."""
    _run_removal_cycle(clients, {})
    total_stalled_calls = sum(client.get_stalled_items.call_count for client in clients)
    assert total_stalled_calls == expect_stalled_call_count
    if expect_remove_called:
        clients[0].remove_stalled.assert_called_once_with(stalled_items)
    else:
        for client in clients:
            client.remove_stalled.assert_not_called()


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
    """Test that _log_killarr_start logs stall category actions."""
    from killarr.main import _log_killarr_start

    with caplog.at_level(logging.INFO):
        _log_killarr_start([MagicMock()], {'stalled': 'remove'})
    assert 'Handling:' in caplog.text
    assert 'stalled=remove' in caplog.text


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
