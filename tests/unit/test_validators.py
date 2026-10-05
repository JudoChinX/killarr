"""Tests for killarr validators."""

# pylint: disable=protected-access
import re
from typing import Any

import pytest

from killarr.validators import SETTINGS_SCHEMA
from killarr.validators import _validate_active_hours
from killarr.validators import validate_global_settings
from killarr.validators import validate_schema_setting
from killarr.validators import validate_stall_action_settings

_validate_active_hours_cases = {
    'valid_same_day': {
        'value': '09:00-17:00',
        'expect_error': False,
    },
    'valid_midnight_crossing': {
        'value': '22:00-06:00',
        'expect_error': False,
    },
    'empty_string_is_allowed': {
        'value': '',
        'expect_error': False,
    },
    'wrong_format_no_colons': {
        'value': '0900-1700',
        'expect_error': True,
    },
    'wrong_format_no_dash': {
        'value': '09:00',
        'expect_error': True,
    },
    'invalid_start_hour': {
        'value': '25:00-06:00',
        'expect_error': True,
    },
    'invalid_end_minute': {
        'value': '22:00-06:99',
        'expect_error': True,
    },
    'start_equals_end': {
        'value': '08:00-08:00',
        'expect_error': True,
    },
}


@pytest.mark.parametrize(
    'value, expect_error',
    [(case['value'], case['expect_error']) for case in _validate_active_hours_cases.values()],
    ids=list(_validate_active_hours_cases.keys()),
)
def test_validate_active_hours(value: str, expect_error: bool) -> None:
    """Test that _validate_active_hours accepts valid formats and rejects invalid ones."""
    if expect_error:
        with pytest.raises(ValueError):
            _validate_active_hours(value)
    else:
        _validate_active_hours(value)


_validate_active_hours_prefix_cases = {
    'invalid_value_uses_prefix': {
        'value': '25:00-06:00',
        'prefix': 'instances.x.killarr',
        'expected_error': "'instances.x.killarr.active_hours' start time '25:00' is not a valid 24-hour time.",
    },
    'valid_value_passes_with_prefix': {
        'value': '22:00-06:00',
        'prefix': 'instances.x.killarr',
        'expected_error': None,
    },
}


@pytest.mark.parametrize(
    'value, prefix, expected_error',
    [(case['value'], case['prefix'], case['expected_error']) for case in _validate_active_hours_prefix_cases.values()],
    ids=list(_validate_active_hours_prefix_cases.keys()),
)
def test_validate_active_hours_prefix(value: str, prefix: str, expected_error: Any) -> None:
    """Test that _validate_active_hours reports the caller-supplied prefix in error messages."""
    if expected_error:
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            _validate_active_hours(value, prefix)
    else:
        _validate_active_hours(value, prefix)


_validate_global_settings_active_hours_cases = {
    'active_hours_valid_passes': {
        'settings': {'active_hours': '22:00-06:00'},
        'expect_error': False,
    },
    'active_hours_invalid_raises': {
        'settings': {'active_hours': 'not-valid'},
        'expect_error': True,
    },
}


@pytest.mark.parametrize(
    'settings, expect_error',
    [(case['settings'], case['expect_error']) for case in _validate_global_settings_active_hours_cases.values()],
    ids=list(_validate_global_settings_active_hours_cases.keys()),
)
def test_validate_global_settings_active_hours(settings: Any, expect_error: bool) -> None:
    """Test that validate_global_settings calls through to _validate_active_hours."""
    if expect_error:
        with pytest.raises(ValueError):
            validate_global_settings(dict(settings), SETTINGS_SCHEMA)
    else:
        validate_global_settings(dict(settings), SETTINGS_SCHEMA)


_validate_global_settings_bool_for_int_cases = {
    'batch_size_true_rejected': {
        'settings': {'batch_size': True},
        'expected_error': "'killarr.batch_size' must be of type int.",
    },
    'retry_interval_minutes_false_rejected': {
        'settings': {'retry_interval_minutes': False},
        'expected_error': "'killarr.retry_interval_minutes' must be of type int.",
    },
    'dead_download_minutes_true_rejected': {
        'settings': {'dead_download_minutes': True},
        'expected_error': "'killarr.dead_download_minutes' must be of type int.",
    },
    'fetch_page_size_true_rejected': {
        'settings': {'fetch_page_size': True},
        'expected_error': "'killarr.fetch_page_size' must be of type int.",
    },
    'dry_run_true_still_accepted': {
        'settings': {'dry_run': True},
        'expected_error': None,
    },
}


@pytest.mark.parametrize(
    'settings, expected_error',
    [(case['settings'], case['expected_error']) for case in _validate_global_settings_bool_for_int_cases.values()],
    ids=list(_validate_global_settings_bool_for_int_cases.keys()),
)
def test_validate_global_settings_bool_for_int(settings: Any, expected_error: Any) -> None:
    """Test that boolean values are rejected for integer settings but accepted for boolean settings."""
    if expected_error:
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            validate_global_settings(dict(settings), SETTINGS_SCHEMA)
    else:
        validate_global_settings(dict(settings), SETTINGS_SCHEMA)


_validate_interleave_instances_cases = {
    'defaults_to_false': {
        'settings': {},
        'expected_value': False,
        'expect_error': False,
    },
    'accepts_true': {
        'settings': {'interleave_instances': True},
        'expected_value': True,
        'expect_error': False,
    },
    'rejects_non_bool': {
        'settings': {'interleave_instances': 'yes'},
        'expected_value': None,
        'expect_error': True,
    },
}


@pytest.mark.parametrize(
    'settings, expected_value, expect_error',
    [
        (case['settings'], case['expected_value'], case['expect_error'])
        for case in _validate_interleave_instances_cases.values()
    ],
    ids=list(_validate_interleave_instances_cases.keys()),
)
def test_validate_interleave_instances(settings: Any, expected_value: Any, expect_error: bool) -> None:
    """Test that interleave_instances defaults to False and rejects non-bool values."""
    settings_copy = dict(settings)
    if expect_error:
        with pytest.raises(ValueError, match='interleave_instances'):
            validate_global_settings(settings_copy, SETTINGS_SCHEMA)
    else:
        validate_global_settings(settings_copy, SETTINGS_SCHEMA)
        assert settings_copy['interleave_instances'] == expected_value


_validate_removal_order_cases = {
    'defaults_to_api_order': {
        'settings': {},
        'expected_value': 'api_order',
        'expect_error': False,
    },
    'accepts_age_ascending': {
        'settings': {'removal_order': 'age_ascending'},
        'expected_value': 'age_ascending',
        'expect_error': False,
    },
    'accepts_age_descending': {
        'settings': {'removal_order': 'age_descending'},
        'expected_value': 'age_descending',
        'expect_error': False,
    },
    'rejects_unknown_value': {
        'settings': {'removal_order': 'alphabetical'},
        'expected_value': None,
        'expect_error': True,
    },
    'rejects_non_string': {
        'settings': {'removal_order': 42},
        'expected_value': None,
        'expect_error': True,
    },
}


@pytest.mark.parametrize(
    'settings, expected_value, expect_error',
    [
        (case['settings'], case['expected_value'], case['expect_error'])
        for case in _validate_removal_order_cases.values()
    ],
    ids=list(_validate_removal_order_cases.keys()),
)
def test_validate_removal_order(settings: Any, expected_value: Any, expect_error: bool) -> None:
    """Test that removal_order defaults to 'api_order' and rejects invalid values."""
    settings_copy = dict(settings)
    if expect_error:
        with pytest.raises(ValueError, match='removal_order'):
            validate_global_settings(settings_copy, SETTINGS_SCHEMA)
    else:
        validate_global_settings(settings_copy, SETTINGS_SCHEMA)
        assert settings_copy['removal_order'] == expected_value


_validate_schema_setting_cases = {
    'type_error_uses_prefix': {
        'setting': 'batch_size',
        'value': 'x',
        'expected_error': "'p.batch_size' must be of type int.",
    },
    'min_value_error_uses_prefix': {
        'setting': 'fetch_page_size',
        'value': 0,
        'expected_error': "'p.fetch_page_size' must be at least 1.",
    },
    'choices_error_uses_prefix': {
        'setting': 'removal_order',
        'value': 'x',
        'expected_error': "'p.removal_order' must be one of:",
    },
    'element_type_error_uses_prefix': {
        'setting': 'include_tags',
        'value': [1],
        'expected_error': "'p.include_tags' must be a list of str values.",
    },
    'validator_delegation_uses_prefix': {
        'setting': 'active_hours',
        'value': '25:00-06:00',
        'expected_error': "'p.active_hours' start time '25:00' is not a valid 24-hour time.",
    },
    'valid_value_passes': {
        'setting': 'batch_size',
        'value': 5,
        'expected_error': None,
    },
}


@pytest.mark.parametrize(
    'setting, value, expected_error',
    [(case['setting'], case['value'], case['expected_error']) for case in _validate_schema_setting_cases.values()],
    ids=list(_validate_schema_setting_cases.keys()),
)
def test_validate_schema_setting(setting: str, value: Any, expected_error: Any) -> None:
    """Test that validate_schema_setting applies every schema rule and reports the supplied prefix."""
    if expected_error:
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            validate_schema_setting(setting, value, SETTINGS_SCHEMA[setting], 'p')
    else:
        validate_schema_setting(setting, value, SETTINGS_SCHEMA[setting], 'p')


_validate_stall_action_settings_cases = {
    'string_value_raises': {
        'settings': {'generic': 'remove'},
        'expect_error': True,
    },
    'valid_dict_remove_only': {
        'settings': {'generic': {'remove': True}},
        'expect_error': False,
    },
    'valid_dict_all_flags': {
        'settings': {'generic': {'remove': True, 'blocklist': True, 'search': False}},
        'expect_error': False,
    },
    'empty_dict_passes': {
        'settings': {'generic': {}},
        'expect_error': False,
    },
    'unknown_key_raises': {
        'settings': {'generic': {'remove': True, 'purge': True}},
        'expect_error': True,
    },
    'non_bool_value_raises': {
        'settings': {'generic': {'remove': 'yes'}},
        'expect_error': True,
    },
    'blocklist_without_remove_raises': {
        'settings': {'generic': {'blocklist': True}},
        'expect_error': True,
    },
    'search_without_remove_raises': {
        'settings': {'generic': {'search': True}},
        'expect_error': True,
    },
    'all_three_enabled_passes': {
        'settings': {'generic': {'remove': True, 'blocklist': True, 'search': True}},
        'expect_error': False,
    },
    'blocklist_with_remove_false_raises': {
        'settings': {'generic': {'remove': False, 'blocklist': True}},
        'expect_error': True,
    },
    'dead_download_valid_flags_passes': {
        'settings': {'dead_download': {'remove': True, 'blocklist': True, 'search': True}},
        'expect_error': False,
    },
    'dead_download_blocklist_without_remove_raises': {
        'settings': {'dead_download': {'blocklist': True}},
        'expect_error': True,
    },
    'unrelated_key_ignored': {
        'settings': {'not_a_category': 'whatever'},
        'expect_error': False,
    },
    'default_string_value_raises': {
        'settings': {'default': 'remove'},
        'expect_error': True,
    },
    'default_valid_dict_passes': {
        'settings': {'default': {'remove': True, 'blocklist': True, 'search': True}},
        'expect_error': False,
    },
    'default_empty_dict_passes': {
        'settings': {'default': {}},
        'expect_error': False,
    },
    'default_blocklist_without_remove_raises': {
        'settings': {'default': {'blocklist': True}},
        'expect_error': True,
    },
    'default_unknown_key_raises': {
        'settings': {'default': {'remove': True, 'purge': True}},
        'expect_error': True,
    },
    'default_search_without_remove_raises': {
        'settings': {'default': {'search': True}},
        'expect_error': True,
    },
}


@pytest.mark.parametrize(
    'settings, expect_error',
    [(case['settings'], case['expect_error']) for case in _validate_stall_action_settings_cases.values()],
    ids=list(_validate_stall_action_settings_cases.keys()),
)
def test_validate_stall_action_settings(settings: Any, expect_error: bool) -> None:
    """Test that validate_stall_action_settings enforces dict-based action flags."""
    if expect_error:
        with pytest.raises(ValueError):
            validate_stall_action_settings(settings)
    else:
        validate_stall_action_settings(settings)


_validate_stall_action_settings_prefix_cases = {
    'not_a_dict_uses_prefix': {
        'settings': {'generic': 'remove'},
        'prefix': 'instances.x.killarr',
        'expected_error': "'instances.x.killarr.generic' must be a dict of action flags, got str.",
    },
    'search_without_remove_uses_prefix': {
        'settings': {'generic': {'search': True}},
        'prefix': 'instances.x.killarr',
        'expected_error': "'instances.x.killarr.generic.search' requires 'remove' to also be True.",
    },
}


@pytest.mark.parametrize(
    'settings, prefix, expected_error',
    [
        (case['settings'], case['prefix'], case['expected_error'])
        for case in _validate_stall_action_settings_prefix_cases.values()
    ],
    ids=list(_validate_stall_action_settings_prefix_cases.keys()),
)
def test_validate_stall_action_settings_prefix(settings: Any, prefix: str, expected_error: str) -> None:
    """Test that validate_stall_action_settings reports the caller-supplied prefix in error messages."""
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        validate_stall_action_settings(settings, prefix)
