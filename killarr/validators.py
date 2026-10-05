"""Validation logic for Killarr configuration."""

import datetime
import re
from typing import Any

from killarr.classifier import StallCategory

VALID_ACTIONS = ('remove', 'blocklist', 'search')
VALID_ARR_TYPES = ('radarr', 'readarr', 'sonarr', 'lidarr', 'whisparr', 'whisparr_v2', 'whisparr_v3')
STALL_CATEGORIES = tuple(category.value for category in StallCategory)
STALL_ACTION_CONFIG_KEYS = STALL_CATEGORIES + ('default',)


def _validate_active_hours(value: str, prefix: str = 'killarr') -> None:
    """Validate the active_hours setting format and component ranges."""
    if not value:
        return
    if not re.match(r'^\d{2}:\d{2}-\d{2}:\d{2}$', value):
        raise ValueError(f"'{prefix}.active_hours' must be in HH:MM-HH:MM format (e.g. '22:00-06:00'), got '{value}'.")
    start_str, end_str = value.split('-')
    for part, label in ((start_str, 'start'), (end_str, 'end')):
        try:
            parse_hhmm(part)
        except ValueError as exc:
            raise ValueError(f"'{prefix}.active_hours' {label} time '{part}' is not a valid 24-hour time.") from exc
    if start_str == end_str:
        raise ValueError(f"'{prefix}.active_hours' start and end times must differ.")


def _validate_setting(
    setting: str,
    value: Any,
    expected_type: type,
    choices: tuple | None = None,
    allow_special_values: bool = False,
    min_value: int | None = None,
    prefix: str = 'killarr',
    element_type: type | None = None,
) -> None:
    """Validate a single setting value against its schema definition."""
    # bool is a subclass of int, so isinstance(True, int) is True; exclude it explicitly.
    if not isinstance(value, expected_type) or (expected_type is int and isinstance(value, bool)):
        raise ValueError(f"'{prefix}.{setting}' must be of type {expected_type.__name__}.")

    if expected_type is int:
        if min_value is not None and value < min_value:
            raise ValueError(f"'{prefix}.{setting}' must be at least {min_value}.")
        if min_value is None:
            limit = -1 if allow_special_values else 0
            if value < limit:
                msg = (
                    f"'{prefix}.{setting}' must be 0 (disabled), -1 (unlimited), or a positive integer."
                    if allow_special_values
                    else f"'{prefix}.{setting}' must be a non-negative integer."
                )
                raise ValueError(msg)

    if expected_type is list and element_type is not None:
        for element in value:
            if not isinstance(element, element_type):
                raise ValueError(f"'{prefix}.{setting}' must be a list of {element_type.__name__} values.")
            if element_type is str and not element:
                raise ValueError(f"'{prefix}.{setting}' entries must not be empty strings.")

    if choices is not None and value not in choices:
        valid_choices = ', '.join(repr(choice) for choice in choices)
        raise ValueError(f"'{prefix}.{setting}' must be one of: {valid_choices}.")


SETTINGS_SCHEMA = {
    'interval': {
        'default': 3600,
        'type': int,
        'min_value': 1,
    },
    'stagger_interval_seconds': {
        'default': 5,
        'type': int,
        'min_value': 0,
    },
    'batch_size': {
        'default': 10,
        'type': int,
        'allow_special_values': True,
    },
    'interleave_instances': {
        'default': False,
        'type': bool,
    },
    'removal_order': {
        'default': 'api_order',
        'type': str,
        'choices': (
            'age_ascending',
            'age_descending',
            'alphabetical_ascending',
            'alphabetical_descending',
            'api_order',
            'random',
        ),
    },
    'retry_interval_minutes': {
        'default': 0,
        'type': int,
        'min_value': 0,
    },
    'dead_download_minutes': {
        'default': 360,
        'type': int,
        'min_value': 0,
    },
    'dry_run': {
        'default': False,
        'type': bool,
    },
    'include_tags': {
        'default': [],
        'type': list,
        'element_type': str,
    },
    'exclude_tags': {
        'default': [],
        'type': list,
        'element_type': str,
    },
    'fetch_page_size': {
        'default': 500,
        'type': int,
        'min_value': 1,
    },
    'fetch_timeout': {
        'default': 30,
        'type': int,
        'min_value': 1,
    },
    'active_hours': {
        'default': '',
        'type': str,
        'validator': _validate_active_hours,
    },
}


def parse_hhmm(token: str) -> datetime.time:
    """Parse an HH:MM token into a datetime.time object.

    Args:
        token: An HH:MM string.

    Returns:
        A datetime.time object.
    """
    return datetime.time.fromisoformat(token)


def validate_global_settings(settings: dict, schema: dict) -> None:
    """Apply defaults and validate all settings against their schema.

    Args:
        settings: The settings dictionary to validate and update.
        schema: The schema dictionary defining validation rules.

    Raises:
        ValueError: If a setting value is invalid.
    """
    for setting, definition in schema.items():
        default = definition['default']
        settings.setdefault(setting, list(default) if isinstance(default, list) else default)
        validate_schema_setting(setting, settings[setting], definition, 'killarr')


def validate_schema_setting(setting: str, value: Any, definition: dict, prefix: str) -> None:
    """Validate one setting value against its schema definition.

    Args:
        setting: Setting name as defined in SETTINGS_SCHEMA.
        value: The value to validate.
        definition: The schema entry for this setting.
        prefix: Dotted config path used in error messages (e.g. 'killarr' or 'instances.Radarr.killarr').

    Raises:
        ValueError: If the value fails type, range, choice, element, or custom validation.
    """
    _validate_setting(
        setting,
        value,
        definition['type'],
        definition.get('choices'),
        allow_special_values=definition.get('allow_special_values', False),
        min_value=definition.get('min_value'),
        prefix=prefix,
        element_type=definition.get('element_type'),
    )
    validator = definition.get('validator')
    if validator is not None:
        validator(value, prefix)


def validate_stall_action_settings(settings: dict, prefix: str = 'killarr') -> None:
    """Validate any stall category action values present in settings.

    Args:
        settings: The settings dictionary containing stall actions.
        prefix: Dotted config path used in error messages.

    Raises:
        ValueError: If an action value is invalid.
    """
    for category in STALL_ACTION_CONFIG_KEYS:
        if category not in settings:
            continue
        value = settings[category]
        if not isinstance(value, dict):
            raise ValueError(f"'{prefix}.{category}' must be a dict of action flags, got {type(value).__name__}.")
        for key, flag in value.items():
            if key not in VALID_ACTIONS:
                valid = ', '.join(repr(action) for action in VALID_ACTIONS)
                raise ValueError(f"'{prefix}.{category}' contains unknown flag '{key}'. Valid flags: {valid}.")
            if not isinstance(flag, bool):
                raise ValueError(f"'{prefix}.{category}.{key}' must be a bool, got {type(flag).__name__}.")
        if value.get('blocklist') is True and value.get('remove') is not True:
            raise ValueError(f"'{prefix}.{category}.blocklist' requires 'remove' to also be True.")
        if value.get('search') is True and value.get('remove') is not True:
            raise ValueError(f"'{prefix}.{category}.search' requires 'remove' to also be True.")
