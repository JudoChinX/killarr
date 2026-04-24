"""Tests for killarr config_parser."""

import logging
import re
import textwrap
from typing import Any

import pytest

from killarr.config_parser import get_setting_default
from killarr.config_parser import load_config
from killarr.config_parser import load_config_from_env
from killarr.config_parser import parse_config
from tests.helpers import assert_config_result

# --- Helpers ---


def make_config(killarr_section: dict | None = None, instances: dict | None = None) -> dict:
    """Build a minimal raw config dict for parse_config."""
    config = {}
    if killarr_section is not None:
        config['killarr'] = killarr_section
    if instances is not None:
        config['instances'] = instances
    else:
        config['instances'] = {
            'radarr': {
                'type': 'radarr',
                'host': 'http://radarr:7878',
                'api_key': 'key',
                'enabled': True,
            }
        }
    return config


MINIMAL_INSTANCE = {
    'radarr': {
        'type': 'radarr',
        'host': 'http://radarr:7878',
        'api_key': 'key',
        'enabled': True,
    }
}


# --- Schema defaults ---

_get_setting_default_cases = {
    'interval': {'setting': 'interval', 'expected': 3600},
    'batch_size': {'setting': 'batch_size', 'expected': 10},
    'dry_run': {'setting': 'dry_run', 'expected': False},
    'stagger_interval_seconds': {'setting': 'stagger_interval_seconds', 'expected': 5},
}


@pytest.mark.parametrize(
    'setting, expected',
    [(case['setting'], case['expected']) for case in _get_setting_default_cases.values()],
    ids=list(_get_setting_default_cases.keys()),
)
def test_get_setting_default(setting: Any, expected: Any) -> None:
    """Test get_setting_default returns the correct schema default for each setting."""
    assert get_setting_default(setting) == expected


def test_get_setting_default_unknown_raises() -> None:
    """Test get_setting_default raises KeyError for an unrecognized setting name."""
    with pytest.raises(KeyError):
        get_setting_default('nonexistent')


# --- parse_config ---

_parse_config_cases = {
    'no_killarr_section_uses_defaults': {
        'config_data': make_config(),
        'expected_result': {
            'global_settings': {
                'interval': 3600,
                'batch_size': 10,
                'dry_run': False,
            },
        },
    },
    'killarr_section_overrides_defaults': {
        'config_data': make_config(killarr_section={'interval': 1800, 'batch_size': 5, 'dry_run': True}),
        'expected_result': {
            'global_settings': {'interval': 1800, 'batch_size': 5, 'dry_run': True},
        },
    },
    'missing_instances_raises': {
        'config_data': {'killarr': {}},
        'expected_error': "Missing required top-level key: 'instances'",
    },
    'not_a_dict_raises': {
        'config_data': 'not a dict',
        'expected_error': 'Configuration file must be a YAML mapping at the top level.',
    },
    'killarr_not_a_dict_raises': {
        'config_data': {'killarr': 'bad', 'instances': MINIMAL_INSTANCE},
        'expected_error': "'killarr' must be a YAML mapping.",
    },
    'instances_not_a_dict_raises': {
        'config_data': {'instances': 'not-a-dict'},
        'expected_error': "'instances' must be a YAML mapping.",
    },
    'instance_config_not_a_dict_raises': {
        'config_data': {'instances': {'r': 'bad'}},
        'expected_error': "Instance 'r' must be a YAML mapping.",
    },
    'instance_missing_type_raises': {
        'config_data': make_config(instances={'r': {'host': 'http://x', 'api_key': 'k', 'enabled': True}}),
        'expected_error': "Missing 'type' field for instance 'r'. Must be one of: radarr, sonarr, lidarr.",
    },
    'invalid_type_raises': {
        'config_data': make_config(
            instances={'r': {'type': 'plex', 'host': 'http://x', 'api_key': 'k', 'enabled': True}}
        ),
        'expected_error': "Invalid type 'plex' for instance 'r'. Must be one of: radarr, sonarr, lidarr.",
    },
    'invalid_batch_size_raises': {
        'config_data': make_config(killarr_section={'batch_size': -2}),
        'expected_error': "'killarr.batch_size' must be 0 (disabled), -1 (unlimited), or a positive integer.",
    },
    'invalid_interval_raises': {
        'config_data': make_config(killarr_section={'interval': 0}),
        'expected_error': "'killarr.interval' must be at least 1.",
    },
    'no_enabled_instances_raises': {
        'config_data': {
            'instances': {'radarr': {'type': 'radarr', 'host': 'http://x', 'api_key': 'k', 'enabled': False}}
        },
        'expected_error': "No instances defined under 'instances'. Add at least one Radarr, Sonarr, or Lidarr instance.",
    },
    'missing_api_key_raises': {
        'config_data': make_config(instances={'r': {'type': 'radarr', 'host': 'http://x', 'enabled': True}}),
        'expected_error': "Missing or empty 'api_key' for instance 'r'.",
    },
    'instance_invalid_weight_raises': {
        'config_data': make_config(
            instances={'r': {'type': 'radarr', 'host': 'http://x', 'api_key': 'k', 'enabled': True, 'weight': -1}}
        ),
        'expected_error': "'weight' for instance 'r' must be a positive number.",
    },
    'wrong_type_for_setting_raises': {
        'config_data': make_config(killarr_section={'interval': 'not-an-int'}),
        'expected_error': "'killarr.interval' must be of type int.",
    },
    'include_tags_non_str_raises': {
        'config_data': make_config(killarr_section={'include_tags': [1, 2]}),
        'expected_error': "'killarr.include_tags' must be a list of str values.",
    },
    'include_tags_empty_str_raises': {
        'config_data': make_config(killarr_section={'include_tags': ['']}),
        'expected_error': "'killarr.include_tags' entries must not be empty strings.",
    },
    'instances_grouped_by_type': {
        'config_data': make_config(
            instances={
                'r1': {'type': 'radarr', 'host': 'http://r1', 'api_key': 'k1', 'enabled': True},
                's1': {'type': 'sonarr', 'host': 'http://s1', 'api_key': 'k2', 'enabled': True},
            }
        ),
        'expected_result': {
            'instances': {
                'radarr': [{'name': 'r1'}],
                'sonarr': [{'name': 's1'}],
            },
        },
    },
    'host_renamed_to_url': {
        'config_data': make_config(),
        'expected_result': {
            'instances': {'radarr': [{'url': 'http://radarr:7878'}]},
        },
    },
    'disabled_instance_excluded': {
        'config_data': make_config(
            instances={
                'active': {'type': 'radarr', 'host': 'http://a', 'api_key': 'k', 'enabled': True},
                'inactive': {'type': 'radarr', 'host': 'http://b', 'api_key': 'k', 'enabled': False},
            }
        ),
        'expected_result': {
            'instances': {'radarr': [{'name': 'active'}]},
        },
    },
    'instance_killarr_override_promoted': {
        'config_data': make_config(
            killarr_section={'batch_size': 10, 'blocklist': True},
            instances={
                'r': {
                    'type': 'radarr',
                    'host': 'http://r',
                    'api_key': 'k',
                    'enabled': True,
                    'killarr': {'batch_size': 3, 'blocklist': False},
                }
            },
        ),
        'expected_result': {
            'instances': {'radarr': [{'batch_size': 3, 'blocklist': False}]},
        },
    },
}


@pytest.mark.parametrize(
    'config_data, expected_error, expected_result',
    [
        (case['config_data'], case.get('expected_error'), case.get('expected_result'))
        for case in _parse_config_cases.values()
    ],
    ids=list(_parse_config_cases.keys()),
)
def test_parse_config(config_data: Any, expected_error: Any, expected_result: Any) -> None:
    """Test parse_config validates configuration structure and values."""
    if expected_error:
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            parse_config(config_data)
    else:
        assert_config_result(parse_config(config_data), expected_result)


def test_parse_config_host_not_in_result() -> None:
    """Test that 'host' is renamed to 'url' and no longer present in the parsed instance."""
    result = parse_config(make_config())
    assert 'host' not in result['instances']['radarr'][0]


def test_parse_config_instance_without_killarr_override_has_no_instance_setting() -> None:
    """Test that instance-level settings are absent when there is no per-instance killarr override."""
    config = make_config(
        killarr_section={'batch_size': 7},
        instances={'r': {'type': 'radarr', 'host': 'http://r', 'api_key': 'k', 'enabled': True}},
    )
    result = parse_config(config)
    assert 'batch_size' not in result['instances']['radarr'][0]


# --- load_config from file ---


def test_load_config_from_file(tmp_path: Any) -> None:
    """Test load_config reads and parses a YAML file correctly."""
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(
        textwrap.dedent("""
        killarr:
          interval: 900
          batch_size: 3

        instances:
          radarr:
            type: radarr
            host: "http://radarr:7878"
            api_key: "abc123"
            enabled: true
    """)
    )
    result = load_config(str(cfg))
    assert result['global_settings']['interval'] == 900
    assert result['global_settings']['batch_size'] == 3
    assert result['instances']['radarr'][0]['api_key'] == 'abc123'


def test_load_config_file_not_found() -> None:
    """Test load_config raises FileNotFoundError when the path does not exist."""
    with pytest.raises(FileNotFoundError):
        load_config('/nonexistent/config.yaml')


def test_load_config_env_var_expansion(tmp_path: Any, monkeypatch: Any) -> None:
    """Test load_config expands ${VAR} placeholders from environment variables."""
    monkeypatch.setenv('MY_API_KEY', 'secret')
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(
        textwrap.dedent("""
        instances:
          radarr:
            type: radarr
            host: "http://radarr:7878"
            api_key: "${MY_API_KEY}"
            enabled: true
    """)
    )
    result = load_config(str(cfg))
    assert result['instances']['radarr'][0]['api_key'] == 'secret'


def test_load_config_env_var_missing_raises(tmp_path: Any) -> None:
    """Test load_config raises ValueError when a ${VAR} placeholder is not set."""
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(
        textwrap.dedent("""
        instances:
          radarr:
            type: radarr
            host: "http://radarr:7878"
            api_key: "${MISSING_VAR}"
            enabled: true
    """)
    )
    with pytest.raises(
        ValueError, match=re.escape("Environment variable 'MISSING_VAR' referenced in config is not set.")
    ):
        load_config(str(cfg))


def test_load_config_rangarr_shared_config_no_killarr_section(tmp_path: Any) -> None:
    """Test killarr gracefully handles a config written for rangarr (no killarr: section)."""
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(
        textwrap.dedent("""
        global:
          interval: 3600
          missing_batch_size: 20

        instances:
          radarr:
            type: radarr
            host: "http://radarr:7878"
            api_key: "key"
            enabled: true
    """)
    )
    result = load_config(str(cfg))
    assert result['global_settings']['interval'] == 3600
    assert result['global_settings']['batch_size'] == 10


def test_load_config_empty_yaml(tmp_path: Any) -> None:
    """Test load_config raises ValueError for an empty YAML file."""
    cfg = tmp_path / 'config.yaml'
    cfg.write_text('')
    with pytest.raises(ValueError):
        load_config(str(cfg))


def test_expand_env_vars_in_list(tmp_path: Any, monkeypatch: Any) -> None:
    """Test load_config expands ${VAR} placeholders inside YAML list values."""
    monkeypatch.setenv('TAG_ONE', 'stalled')
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(
        textwrap.dedent("""
        killarr:
          include_tags:
            - "${TAG_ONE}"
        instances:
          radarr:
            type: radarr
            host: "http://r"
            api_key: "k"
            enabled: true
    """)
    )
    result = load_config(str(cfg))
    assert result['global_settings']['include_tags'] == ['stalled']


# --- load_config_from_env ---

_load_config_from_env_cases = {
    'basic_instance_and_globals': {
        'env_vars': {
            'KILLARR_CONFIG_SOURCE': 'env',
            'KILLARR_GLOBAL_INTERVAL': '1800',
            'KILLARR_GLOBAL_BATCH_SIZE': '5',
            'KILLARR_INSTANCE_0_NAME': 'MyRadarr',
            'KILLARR_INSTANCE_0_TYPE': 'radarr',
            'KILLARR_INSTANCE_0_URL': 'http://radarr:7878',
            'KILLARR_INSTANCE_0_API_KEY': 'envkey',
        },
        'expected_result': {
            'global_settings': {'interval': 1800, 'batch_size': 5},
            'instances': {'radarr': [{'name': 'MyRadarr', 'api_key': 'envkey'}]},
        },
    },
    'defaults_when_no_globals': {
        'env_vars': {
            'KILLARR_INSTANCE_0_NAME': 'R',
            'KILLARR_INSTANCE_0_TYPE': 'radarr',
            'KILLARR_INSTANCE_0_URL': 'http://r:7878',
            'KILLARR_INSTANCE_0_API_KEY': 'k',
        },
        'expected_result': {
            'global_settings': {'interval': 3600, 'dry_run': False},
        },
    },
    'multiple_instances': {
        'env_vars': {
            'KILLARR_INSTANCE_0_NAME': 'Radarr',
            'KILLARR_INSTANCE_0_TYPE': 'radarr',
            'KILLARR_INSTANCE_0_URL': 'http://r',
            'KILLARR_INSTANCE_0_API_KEY': 'k1',
            'KILLARR_INSTANCE_1_NAME': 'Sonarr',
            'KILLARR_INSTANCE_1_TYPE': 'sonarr',
            'KILLARR_INSTANCE_1_URL': 'http://s',
            'KILLARR_INSTANCE_1_API_KEY': 'k2',
        },
        'expected_result': {
            'instances': {'radarr': [{'name': 'Radarr'}], 'sonarr': [{'name': 'Sonarr'}]},
        },
    },
    'bool_parsing': {
        'env_vars': {
            'KILLARR_GLOBAL_DRY_RUN': 'true',
            'KILLARR_GLOBAL_BLOCKLIST': 'false',
            'KILLARR_INSTANCE_0_NAME': 'R',
            'KILLARR_INSTANCE_0_TYPE': 'radarr',
            'KILLARR_INSTANCE_0_URL': 'http://r',
            'KILLARR_INSTANCE_0_API_KEY': 'k',
        },
        'expected_result': {
            'global_settings': {'dry_run': True, 'blocklist': False},
        },
    },
    'duplicate_name_raises': {
        'env_vars': {
            'KILLARR_INSTANCE_0_NAME': 'SameName',
            'KILLARR_INSTANCE_0_TYPE': 'radarr',
            'KILLARR_INSTANCE_0_URL': 'http://r',
            'KILLARR_INSTANCE_0_API_KEY': 'k',
            'KILLARR_INSTANCE_1_NAME': 'SameName',
            'KILLARR_INSTANCE_1_TYPE': 'radarr',
            'KILLARR_INSTANCE_1_URL': 'http://r',
            'KILLARR_INSTANCE_1_API_KEY': 'k',
        },
        'expected_error': "Duplicate instance name 'SameName' found at index 1.",
    },
    'list_type_global': {
        'env_vars': {
            'KILLARR_GLOBAL_INCLUDE_TAGS': 'stalled,broken',
            'KILLARR_INSTANCE_0_NAME': 'R',
            'KILLARR_INSTANCE_0_TYPE': 'radarr',
            'KILLARR_INSTANCE_0_URL': 'http://r',
            'KILLARR_INSTANCE_0_API_KEY': 'k',
        },
        'expected_result': {
            'global_settings': {'include_tags': ['stalled', 'broken']},
        },
    },
    'float_weight_parsed': {
        'env_vars': {
            'KILLARR_INSTANCE_0_NAME': 'R',
            'KILLARR_INSTANCE_0_TYPE': 'radarr',
            'KILLARR_INSTANCE_0_URL': 'http://r',
            'KILLARR_INSTANCE_0_API_KEY': 'k',
            'KILLARR_INSTANCE_0_WEIGHT': '1.5',
        },
        'expected_result': {
            'instances': {'radarr': [{'weight': 1.5}]},
        },
    },
}


@pytest.mark.parametrize(
    'env_vars, expected_error, expected_result',
    [
        (case['env_vars'], case.get('expected_error'), case.get('expected_result'))
        for case in _load_config_from_env_cases.values()
    ],
    ids=list(_load_config_from_env_cases.keys()),
)
def test_load_config_from_env(monkeypatch: Any, env_vars: Any, expected_error: Any, expected_result: Any) -> None:
    """Test load_config_from_env reads instances and global settings from environment variables."""
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    if expected_error:
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            load_config_from_env()
    else:
        assert_config_result(load_config_from_env(), expected_result)


def test_load_config_from_env_empty_name_skipped(monkeypatch: Any, caplog: Any) -> None:
    """Test load_config_from_env skips instances with empty names and logs a warning."""
    monkeypatch.setenv('KILLARR_INSTANCE_0_NAME', '')
    monkeypatch.setenv('KILLARR_INSTANCE_0_TYPE', 'radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_URL', 'http://r')
    monkeypatch.setenv('KILLARR_INSTANCE_0_API_KEY', 'k')
    monkeypatch.setenv('KILLARR_INSTANCE_1_NAME', 'R')
    monkeypatch.setenv('KILLARR_INSTANCE_1_TYPE', 'radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_1_URL', 'http://r')
    monkeypatch.setenv('KILLARR_INSTANCE_1_API_KEY', 'k')
    with caplog.at_level(logging.WARNING):
        result = load_config_from_env()
    assert len(result['instances']['radarr']) == 1
    assert 'Skipping' in caplog.text


# --- KILLARR_INSTANCE_SOURCE=shared ---

_load_config_from_env_shared_cases = {
    'reads_rangarr_instances_when_source_shared': {
        'env_vars': {
            'KILLARR_INSTANCE_SOURCE': 'shared',
            'RANGARR_INSTANCE_0_NAME': 'Movies',
            'RANGARR_INSTANCE_0_TYPE': 'radarr',
            'RANGARR_INSTANCE_0_URL': 'http://radarr:7878',
            'RANGARR_INSTANCE_0_API_KEY': 'sharedkey',
        },
        'expected_result': {
            'instances': {'radarr': [{'name': 'Movies', 'api_key': 'sharedkey'}]},
        },
    },
    'killarr_instances_ignored_when_source_shared': {
        'env_vars': {
            'KILLARR_INSTANCE_SOURCE': 'shared',
            'KILLARR_INSTANCE_0_NAME': 'ShouldBeIgnored',
            'KILLARR_INSTANCE_0_TYPE': 'radarr',
            'KILLARR_INSTANCE_0_URL': 'http://r',
            'KILLARR_INSTANCE_0_API_KEY': 'k',
            'RANGARR_INSTANCE_0_NAME': 'Movies',
            'RANGARR_INSTANCE_0_TYPE': 'radarr',
            'RANGARR_INSTANCE_0_URL': 'http://radarr:7878',
            'RANGARR_INSTANCE_0_API_KEY': 'sharedkey',
        },
        'expected_result': {
            'instances': {'radarr': [{'name': 'Movies'}]},
        },
    },
    'killarr_globals_apply_with_shared_source': {
        'env_vars': {
            'KILLARR_INSTANCE_SOURCE': 'shared',
            'KILLARR_GLOBAL_DRY_RUN': 'true',
            'KILLARR_GLOBAL_BATCH_SIZE': '3',
            'RANGARR_INSTANCE_0_NAME': 'TV',
            'RANGARR_INSTANCE_0_TYPE': 'sonarr',
            'RANGARR_INSTANCE_0_URL': 'http://sonarr:8989',
            'RANGARR_INSTANCE_0_API_KEY': 'k',
        },
        'expected_result': {
            'global_settings': {'dry_run': True, 'batch_size': 3},
            'instances': {'sonarr': [{'name': 'TV'}]},
        },
    },
    'multiple_rangarr_instances_loaded': {
        'env_vars': {
            'KILLARR_INSTANCE_SOURCE': 'shared',
            'RANGARR_INSTANCE_0_NAME': 'Radarr',
            'RANGARR_INSTANCE_0_TYPE': 'radarr',
            'RANGARR_INSTANCE_0_URL': 'http://radarr:7878',
            'RANGARR_INSTANCE_0_API_KEY': 'k1',
            'RANGARR_INSTANCE_1_NAME': 'Sonarr',
            'RANGARR_INSTANCE_1_TYPE': 'sonarr',
            'RANGARR_INSTANCE_1_URL': 'http://sonarr:8989',
            'RANGARR_INSTANCE_1_API_KEY': 'k2',
        },
        'expected_result': {
            'instances': {'radarr': [{'name': 'Radarr'}], 'sonarr': [{'name': 'Sonarr'}]},
        },
    },
    'source_value_matched_case_insensitively': {
        'env_vars': {
            'KILLARR_INSTANCE_SOURCE': 'SHARED',
            'RANGARR_INSTANCE_0_NAME': 'Movies',
            'RANGARR_INSTANCE_0_TYPE': 'radarr',
            'RANGARR_INSTANCE_0_URL': 'http://radarr:7878',
            'RANGARR_INSTANCE_0_API_KEY': 'k',
        },
        'expected_result': {
            'instances': {'radarr': [{'name': 'Movies'}]},
        },
    },
    'no_source_uses_killarr_instances': {
        'env_vars': {
            'KILLARR_INSTANCE_0_NAME': 'Movies',
            'KILLARR_INSTANCE_0_TYPE': 'radarr',
            'KILLARR_INSTANCE_0_URL': 'http://radarr:7878',
            'KILLARR_INSTANCE_0_API_KEY': 'k',
        },
        'expected_result': {
            'instances': {'radarr': [{'name': 'Movies'}]},
        },
    },
}


@pytest.mark.parametrize(
    'env_vars, expected_result',
    [(case['env_vars'], case['expected_result']) for case in _load_config_from_env_shared_cases.values()],
    ids=list(_load_config_from_env_shared_cases.keys()),
)
def test_load_config_from_env_shared(monkeypatch: Any, env_vars: Any, expected_result: Any) -> None:
    """Test KILLARR_INSTANCE_SOURCE=shared reads RANGARR_INSTANCE_* for instance definitions."""
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    assert_config_result(load_config_from_env(), expected_result)


# --- Stall action settings ---


def test_parse_config_with_actions() -> None:
    """Test parse_config accepts and preserves valid stall category action settings."""
    config = {
        'instances': {'r': {'type': 'radarr', 'url': 'http://h', 'api_key': 'k', 'enabled': True}},
        'killarr': {'no_upgrade': 'ignore', 'stalled': 'blocklist'},
    }
    result = parse_config(config)
    assert result['global_settings']['no_upgrade'] == 'ignore'
    assert result['global_settings']['stalled'] == 'blocklist'


def test_parse_config_invalid_action() -> None:
    """Test parse_config raises ValueError when a stall category has an unrecognised action value."""
    config = {
        'instances': {'r': {'type': 'radarr', 'url': 'http://h', 'api_key': 'k', 'enabled': True}},
        'killarr': {'stalled': 'invalid_action'},
    }
    with pytest.raises(ValueError, match='must be one of'):
        parse_config(config)
