"""Tests for killarr config_parser."""

import os
import textwrap

import pytest
import yaml

from killarr.config_parser import SETTINGS_SCHEMA
from killarr.config_parser import get_setting_default
from killarr.config_parser import load_config
from killarr.config_parser import load_config_from_env
from killarr.config_parser import parse_config


# --- Helpers ---

def make_config(killarr_section=None, instances=None):
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

def test_get_setting_default_interval():
    assert get_setting_default('interval') == 3600

def test_get_setting_default_batch_size():
    assert get_setting_default('batch_size') == 10

def test_get_setting_default_remove_from_client():
    assert get_setting_default('remove_from_client') is True

def test_get_setting_default_blocklist():
    assert get_setting_default('blocklist') is True

def test_get_setting_default_search_again():
    assert get_setting_default('search_again') is True

def test_get_setting_default_dry_run():
    assert get_setting_default('dry_run') is False

def test_get_setting_default_stagger():
    assert get_setting_default('stagger_interval_seconds') == 5

def test_get_setting_default_unknown_raises():
    with pytest.raises(KeyError):
        get_setting_default('nonexistent')


# --- parse_config: no killarr section (shared config, rangarr-only) ---

def test_parse_config_no_killarr_section_uses_defaults():
    config = parse_config(make_config())
    gs = config['global_settings']
    assert gs['interval'] == 3600
    assert gs['batch_size'] == 10
    assert gs['remove_from_client'] is True
    assert gs['blocklist'] is True
    assert gs['search_again'] is True
    assert gs['dry_run'] is False

def test_parse_config_killarr_section_overrides_defaults():
    config = parse_config(make_config(killarr_section={'interval': 1800, 'batch_size': 5, 'dry_run': True}))
    gs = config['global_settings']
    assert gs['interval'] == 1800
    assert gs['batch_size'] == 5
    assert gs['dry_run'] is True
    # Un-touched settings still use defaults
    assert gs['remove_from_client'] is True

def test_parse_config_missing_instances_raises():
    with pytest.raises(ValueError, match="Missing required top-level key: 'instances'"):
        parse_config({'killarr': {}})

def test_parse_config_not_a_dict_raises():
    with pytest.raises(ValueError, match='YAML mapping'):
        parse_config('not a dict')

def test_parse_config_killarr_not_a_dict_raises():
    with pytest.raises(ValueError, match="'killarr' must be a YAML mapping"):
        parse_config({'killarr': 'bad', 'instances': MINIMAL_INSTANCE})

def test_parse_config_invalid_batch_size_raises():
    with pytest.raises(ValueError):
        parse_config(make_config(killarr_section={'batch_size': -2}))

def test_parse_config_invalid_interval_raises():
    with pytest.raises(ValueError):
        parse_config(make_config(killarr_section={'interval': 0}))

def test_parse_config_no_enabled_instances_raises():
    config = {
        'instances': {
            'radarr': {'type': 'radarr', 'host': 'http://x', 'api_key': 'k', 'enabled': False}
        }
    }
    with pytest.raises(ValueError, match='No instances'):
        parse_config(config)

def test_parse_config_missing_api_key_raises():
    config = make_config(instances={'r': {'type': 'radarr', 'host': 'http://x', 'enabled': True}})
    with pytest.raises(ValueError, match="'api_key'"):
        parse_config(config)

def test_parse_config_invalid_type_raises():
    config = make_config(instances={'r': {'type': 'plex', 'host': 'http://x', 'api_key': 'k', 'enabled': True}})
    with pytest.raises(ValueError, match="Invalid type"):
        parse_config(config)

def test_parse_config_instances_grouped_by_type():
    config = make_config(instances={
        'r1': {'type': 'radarr', 'host': 'http://r1', 'api_key': 'k1', 'enabled': True},
        's1': {'type': 'sonarr', 'host': 'http://s1', 'api_key': 'k2', 'enabled': True},
    })
    result = parse_config(config)
    assert len(result['instances']['radarr']) == 1
    assert len(result['instances']['sonarr']) == 1
    assert result['instances']['radarr'][0]['name'] == 'r1'
    assert result['instances']['sonarr'][0]['name'] == 's1'

def test_parse_config_host_renamed_to_url():
    result = parse_config(make_config())
    assert result['instances']['radarr'][0]['url'] == 'http://radarr:7878'
    assert 'host' not in result['instances']['radarr'][0]

def test_parse_config_disabled_instance_excluded():
    config = make_config(instances={
        'active': {'type': 'radarr', 'host': 'http://a', 'api_key': 'k', 'enabled': True},
        'inactive': {'type': 'radarr', 'host': 'http://b', 'api_key': 'k', 'enabled': False},
    })
    result = parse_config(config)
    assert len(result['instances']['radarr']) == 1
    assert result['instances']['radarr'][0]['name'] == 'active'


# --- Instance-level killarr overrides ---

def test_parse_config_instance_killarr_override_promoted():
    config = make_config(
        killarr_section={'batch_size': 10, 'blocklist': True},
        instances={
            'r': {
                'type': 'radarr', 'host': 'http://r', 'api_key': 'k', 'enabled': True,
                'killarr': {'batch_size': 3, 'blocklist': False},
            }
        },
    )
    result = parse_config(config)
    inst = result['instances']['radarr'][0]
    assert inst['batch_size'] == 3
    assert inst['blocklist'] is False

def test_parse_config_instance_without_killarr_override_uses_global():
    config = make_config(
        killarr_section={'batch_size': 7},
        instances={
            'r': {'type': 'radarr', 'host': 'http://r', 'api_key': 'k', 'enabled': True}
        },
    )
    result = parse_config(config)
    # Instance has no killarr override, no batch_size at instance level
    assert 'batch_size' not in result['instances']['radarr'][0]


# --- load_config from file ---

def test_load_config_from_file(tmp_path):
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(textwrap.dedent("""
        killarr:
          interval: 900
          batch_size: 3

        instances:
          radarr:
            type: radarr
            host: "http://radarr:7878"
            api_key: "abc123"
            enabled: true
    """))
    result = load_config(str(cfg))
    assert result['global_settings']['interval'] == 900
    assert result['global_settings']['batch_size'] == 3
    assert result['instances']['radarr'][0]['api_key'] == 'abc123'

def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config('/nonexistent/config.yaml')

def test_load_config_env_var_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv('MY_API_KEY', 'secret')
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(textwrap.dedent("""
        instances:
          radarr:
            type: radarr
            host: "http://radarr:7878"
            api_key: "${MY_API_KEY}"
            enabled: true
    """))
    result = load_config(str(cfg))
    assert result['instances']['radarr'][0]['api_key'] == 'secret'

def test_load_config_env_var_missing_raises(tmp_path):
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(textwrap.dedent("""
        instances:
          radarr:
            type: radarr
            host: "http://radarr:7878"
            api_key: "${MISSING_VAR}"
            enabled: true
    """))
    with pytest.raises(ValueError, match="'MISSING_VAR'"):
        load_config(str(cfg))

def test_load_config_rangarr_shared_config_no_killarr_section(tmp_path):
    """Killarr gracefully handles a config written for rangarr (no killarr: section)."""
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(textwrap.dedent("""
        global:
          interval: 3600
          missing_batch_size: 20

        instances:
          radarr:
            type: radarr
            host: "http://radarr:7878"
            api_key: "key"
            enabled: true
    """))
    result = load_config(str(cfg))
    # Falls back to all killarr defaults
    assert result['global_settings']['interval'] == 3600
    assert result['global_settings']['batch_size'] == 10


# --- load_config_from_env ---

def test_load_config_from_env_basic(monkeypatch):
    monkeypatch.setenv('KILLARR_CONFIG_SOURCE', 'env')
    monkeypatch.setenv('KILLARR_GLOBAL_INTERVAL', '1800')
    monkeypatch.setenv('KILLARR_GLOBAL_BATCH_SIZE', '5')
    monkeypatch.setenv('KILLARR_INSTANCE_0_NAME', 'MyRadarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_TYPE', 'radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_URL', 'http://radarr:7878')
    monkeypatch.setenv('KILLARR_INSTANCE_0_API_KEY', 'envkey')
    result = load_config_from_env()
    assert result['global_settings']['interval'] == 1800
    assert result['global_settings']['batch_size'] == 5
    assert result['instances']['radarr'][0]['name'] == 'MyRadarr'
    assert result['instances']['radarr'][0]['api_key'] == 'envkey'

def test_load_config_from_env_defaults_when_no_globals(monkeypatch):
    monkeypatch.setenv('KILLARR_INSTANCE_0_NAME', 'R')
    monkeypatch.setenv('KILLARR_INSTANCE_0_TYPE', 'radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_URL', 'http://r:7878')
    monkeypatch.setenv('KILLARR_INSTANCE_0_API_KEY', 'k')
    result = load_config_from_env()
    assert result['global_settings']['interval'] == 3600
    assert result['global_settings']['remove_from_client'] is True

def test_load_config_from_env_multiple_instances(monkeypatch):
    monkeypatch.setenv('KILLARR_INSTANCE_0_NAME', 'Radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_TYPE', 'radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_URL', 'http://r')
    monkeypatch.setenv('KILLARR_INSTANCE_0_API_KEY', 'k1')
    monkeypatch.setenv('KILLARR_INSTANCE_1_NAME', 'Sonarr')
    monkeypatch.setenv('KILLARR_INSTANCE_1_TYPE', 'sonarr')
    monkeypatch.setenv('KILLARR_INSTANCE_1_URL', 'http://s')
    monkeypatch.setenv('KILLARR_INSTANCE_1_API_KEY', 'k2')
    result = load_config_from_env()
    assert len(result['instances']['radarr']) == 1
    assert len(result['instances']['sonarr']) == 1

def test_load_config_from_env_bool_parsing(monkeypatch):
    monkeypatch.setenv('KILLARR_GLOBAL_DRY_RUN', 'true')
    monkeypatch.setenv('KILLARR_GLOBAL_BLOCKLIST', 'false')
    monkeypatch.setenv('KILLARR_INSTANCE_0_NAME', 'R')
    monkeypatch.setenv('KILLARR_INSTANCE_0_TYPE', 'radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_URL', 'http://r')
    monkeypatch.setenv('KILLARR_INSTANCE_0_API_KEY', 'k')
    result = load_config_from_env()
    assert result['global_settings']['dry_run'] is True
    assert result['global_settings']['blocklist'] is False

def test_load_config_from_env_empty_name_skipped(monkeypatch, caplog):
    import logging
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

def test_load_config_from_env_duplicate_name_raises(monkeypatch):
    for i in range(2):
        monkeypatch.setenv(f'KILLARR_INSTANCE_{i}_NAME', 'SameName')
        monkeypatch.setenv(f'KILLARR_INSTANCE_{i}_TYPE', 'radarr')
        monkeypatch.setenv(f'KILLARR_INSTANCE_{i}_URL', 'http://r')
        monkeypatch.setenv(f'KILLARR_INSTANCE_{i}_API_KEY', 'k')
    with pytest.raises(ValueError, match="Duplicate"):
        load_config_from_env()

def test_load_config_from_env_list_type_global(monkeypatch):
    monkeypatch.setenv('KILLARR_GLOBAL_INCLUDE_TAGS', 'stalled,broken')
    monkeypatch.setenv('KILLARR_INSTANCE_0_NAME', 'R')
    monkeypatch.setenv('KILLARR_INSTANCE_0_TYPE', 'radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_URL', 'http://r')
    monkeypatch.setenv('KILLARR_INSTANCE_0_API_KEY', 'k')
    result = load_config_from_env()
    assert result['global_settings']['include_tags'] == ['stalled', 'broken']


# --- Additional coverage tests ---

def test_parse_config_instances_not_a_dict_raises():
    with pytest.raises(ValueError, match="'instances' must be a YAML mapping"):
        parse_config({'instances': 'not-a-dict'})

def test_parse_config_instance_config_not_a_dict_raises():
    with pytest.raises(ValueError):
        parse_config({'instances': {'r': 'bad'}})

def test_parse_config_instance_missing_type_raises():
    config = make_config(instances={'r': {'host': 'http://x', 'api_key': 'k', 'enabled': True}})
    with pytest.raises(ValueError, match="Missing 'type'"):
        parse_config(config)

def test_parse_config_instance_invalid_weight_raises():
    config = make_config(instances={
        'r': {'type': 'radarr', 'host': 'http://x', 'api_key': 'k', 'enabled': True, 'weight': -1}
    })
    with pytest.raises(ValueError, match="'weight'"):
        parse_config(config)

def test_parse_config_wrong_type_for_setting_raises():
    with pytest.raises(ValueError, match="must be of type"):
        parse_config(make_config(killarr_section={'interval': 'not-an-int'}))

def test_parse_config_include_tags_non_str_raises():
    with pytest.raises(ValueError):
        parse_config(make_config(killarr_section={'include_tags': [1, 2]}))

def test_parse_config_include_tags_empty_str_raises():
    with pytest.raises(ValueError):
        parse_config(make_config(killarr_section={'include_tags': ['']}))

def test_load_config_empty_yaml(tmp_path):
    cfg = tmp_path / 'config.yaml'
    cfg.write_text('')
    with pytest.raises(ValueError):
        load_config(str(cfg))

def test_expand_env_vars_in_list(tmp_path, monkeypatch):
    monkeypatch.setenv('TAG_ONE', 'stalled')
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(textwrap.dedent("""
        killarr:
          include_tags:
            - "${TAG_ONE}"
        instances:
          radarr:
            type: radarr
            host: "http://r"
            api_key: "k"
            enabled: true
    """))
    result = load_config(str(cfg))
    assert result['global_settings']['include_tags'] == ['stalled']

def test_parse_env_value_float(monkeypatch):
    monkeypatch.setenv('KILLARR_INSTANCE_0_NAME', 'R')
    monkeypatch.setenv('KILLARR_INSTANCE_0_TYPE', 'radarr')
    monkeypatch.setenv('KILLARR_INSTANCE_0_URL', 'http://r')
    monkeypatch.setenv('KILLARR_INSTANCE_0_API_KEY', 'k')
    monkeypatch.setenv('KILLARR_INSTANCE_0_WEIGHT', '1.5')
    result = load_config_from_env()
    assert result['instances']['radarr'][0]['weight'] == 1.5
