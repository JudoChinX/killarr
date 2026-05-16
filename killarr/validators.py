"""Validation logic for Killarr configuration."""

import datetime
import re
from typing import Any

from killarr.classifier import StallCategory

VALID_ACTIONS = ('remove', 'blocklist', 'search')
VALID_ARR_TYPES = ('radarr', 'sonarr', 'lidarr')
STALL_CATEGORIES = tuple(category.value for category in StallCategory)
STALL_ACTION_CONFIG_KEYS = STALL_CATEGORIES + ('default',)


def _validate_active_hours(value: str) -> None:
    """Validate the active_hours setting format and component ranges."""
    if not value:
        return
    if not re.match(r'^\d{2}:\d{2}-\d{2}:\d{2}$', value):
        raise ValueError(f"'killarr.active_hours' must be in HH:MM-HH:MM format (e.g. '22:00-06:00'), got '{value}'.")
    start_str, end_str = value.split('-')
    for part, label in ((start_str, 'start'), (end_str, 'end')):
        try:
            parse_hhmm(part)
        except ValueError as exc:
            raise ValueError(f"'killarr.active_hours' {label} time '{part}' is not a valid 24-hour time.") from exc
    if start_str == end_str:
        raise ValueError("'killarr.active_hours' start and end times must differ.")


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
    if not isinstance(value, expected_type):
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
        'choices': ('age_ascending', 'age_descending', 'api_order'),
    },
    'retry_interval_minutes': {
        'default': 0,
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
        _validate_setting(
            setting,
            settings[setting],
            definition['type'],
            definition.get('choices'),
            allow_special_values=definition.get('allow_special_values', False),
            min_value=definition.get('min_value'),
            element_type=definition.get('element_type'),
        )
        validator = definition.get('validator')
        if validator is not None:
            validator(settings[setting])


def validate_stall_action_settings(settings: dict) -> None:
    """Validate any stall category action values present in settings.

    Args:
        settings: The settings dictionary containing stall actions.

    Raises:
        ValueError: If an action value is invalid.
    """
    for category in STALL_ACTION_CONFIG_KEYS:
        if category not in settings:
            continue
        value = settings[category]
        if not isinstance(value, dict):
            raise ValueError(f"'killarr.{category}' must be a dict of action flags, got {type(value).__name__}.")
        for key, flag in value.items():
            if key not in VALID_ACTIONS:
                valid = ', '.join(repr(action) for action in VALID_ACTIONS)
                raise ValueError(f"'killarr.{category}' contains unknown flag '{key}'. Valid flags: {valid}.")
            if not isinstance(flag, bool):
                raise ValueError(f"'killarr.{category}.{key}' must be a bool, got {type(flag).__name__}.")
        if value.get('blocklist') is True and value.get('remove') is not True:
            raise ValueError(f"'killarr.{category}.blocklist' requires 'remove' to also be True.")
        if value.get('search') is True and value.get('remove') is not True:
            raise ValueError(f"'killarr.{category}.search' requires 'remove' to also be True.")
