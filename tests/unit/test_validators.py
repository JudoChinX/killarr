"""Tests for killarr validators."""

# pylint: disable=protected-access
from typing import Any

import pytest

from killarr.validators import _validate_active_hours
from killarr.validators import validate_global_settings

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
    from killarr.validators import SETTINGS_SCHEMA

    if expect_error:
        with pytest.raises(ValueError):
            validate_global_settings(dict(settings), SETTINGS_SCHEMA)
    else:
        validate_global_settings(dict(settings), SETTINGS_SCHEMA)
