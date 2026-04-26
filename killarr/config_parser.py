"""Configuration loader and validator for Killarr."""

import logging
import os
import re
from typing import Any

import yaml

from killarr.validators import SETTINGS_SCHEMA
from killarr.validators import VALID_ARR_TYPES
from killarr.validators import validate_global_settings
from killarr.validators import validate_stall_action_settings

_LOGGER = logging.getLogger(__name__)

REQUIRED_TOP_LEVEL = ('instances',)


def _expand_env_var(match: re.Match) -> str:
    """Resolve a regex match group to its environment variable value."""
    name = match.group(1)
    val = os.environ.get(name)
    if val is None:
        raise ValueError(f"Environment variable '{name}' referenced in config is not set.")
    return val


def _expand_env_vars(obj: Any) -> Any:
    """Recursively expand ${VAR} placeholders in string values using environment variables."""
    if isinstance(obj, dict):
        result = {key: _expand_env_vars(val) for key, val in obj.items()}
    elif isinstance(obj, list):
        result = [_expand_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        result = re.sub(r'\$\{([^}]+)\}', _expand_env_var, obj)
    else:
        result = obj
    return result


def _parse_env_value(value: str) -> Any:
    """Convert an environment string value to bool, int, float, or string."""
    val_lower = value.lower()
    result: Any = value
    if val_lower == 'true':
        result = True
    elif val_lower == 'false':
        result = False
    elif re.match(r'^-?\d+$', value):
        result = int(value)
    elif re.match(r'^-?\d+\.\d+$', value):
        result = float(value)
    return result


def _parse_instance(name: str, config: dict) -> tuple[str, dict] | None:
    """Parse and validate a single instance configuration entry."""
    instance = config.copy()
    # Extract killarr-specific per-instance overrides before processing connection fields
    killarr_overrides = instance.pop('killarr', {})
    if 'host' in instance:
        instance['url'] = instance.pop('host')
    inst_type = str(instance.pop('type', None) or '').lower()
    if not inst_type:
        raise ValueError(f"Missing 'type' field for instance '{name}'. Must be one of: {', '.join(VALID_ARR_TYPES)}.")
    if inst_type not in VALID_ARR_TYPES:
        raise ValueError(
            f"Invalid type '{inst_type}' for instance '{name}'. Must be one of: {', '.join(VALID_ARR_TYPES)}."
        )
    instance['name'] = name
    for field in ('url', 'api_key'):
        if not instance.get(field):
            raise ValueError(f"Missing or empty '{field}' for instance '{name}'.")
    instance.setdefault('weight', 1)
    if not isinstance(instance['weight'], (int, float)) or instance['weight'] <= 0:
        raise ValueError(f"'weight' for instance '{name}' must be a positive number.")
    result = None
    if instance.get('enabled', False):
        # Promote killarr overrides to top-level so main.py can pick them up
        instance.update(killarr_overrides)
        result = (inst_type, instance)
    return result


def get_setting_default(setting: str) -> Any:
    """Return the schema default for a named setting.

    Args:
        setting: Setting name as defined in SETTINGS_SCHEMA.

    Returns:
        The default value.

    Raises:
        KeyError: If setting is not in the schema.
    """
    return SETTINGS_SCHEMA[setting]['default']


def load_config(path: str) -> dict:
    """Load and validate a YAML configuration file.

    Args:
        path: Filesystem path to config.yaml.

    Returns:
        Parsed and validated configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required keys are missing or values are invalid.
    """
    with open(path, encoding='utf-8') as file:
        config = yaml.safe_load(file)

    if config is None:
        config = {}

    config = _expand_env_vars(config)
    return parse_config(config)


def load_config_from_env() -> dict:
    """Load configuration entirely from environment variables.

    Reads ``KILLARR_GLOBAL_*`` for global settings and
    ``KILLARR_INSTANCE_{index}_*`` for instance definitions.

    When ``KILLARR_INSTANCE_SOURCE=shared`` is set, instance definitions are
    read from ``RANGARR_INSTANCE_{index}_*`` variables instead, allowing
    Killarr to share instance configuration with Rangarr without duplication.

    Returns:
        Validated and normalized configuration dictionary.

    Raises:
        ValueError: If required instance fields are missing or values are invalid.
    """
    config: dict = {'instances': {}}
    killarr_section: dict = {}
    instance_data: dict[int, dict] = {}

    instance_source = os.environ.get('KILLARR_INSTANCE_SOURCE', '').lower().strip()
    instance_prefix = 'RANGARR_INSTANCE_' if instance_source == 'shared' else 'KILLARR_INSTANCE_'

    for key, value in os.environ.items():
        if key.startswith('KILLARR_GLOBAL_'):
            setting_name = key.removeprefix('KILLARR_GLOBAL_').lower()
            schema_entry = SETTINGS_SCHEMA.get(setting_name)
            if schema_entry and schema_entry.get('type') is list:
                killarr_section[setting_name] = [item.strip() for item in value.split(',') if item.strip()]
            else:
                killarr_section[setting_name] = _parse_env_value(value)
        elif key.startswith(instance_prefix):
            remainder = key.removeprefix(instance_prefix)
            match = re.match(r'(?P<index>\d+)_(?P<field>.+)', remainder)
            if match:
                index = int(match.group('index'))
                field = match.group('field').lower()
                instance_data.setdefault(index, {})[field] = _parse_env_value(value)

    config['killarr'] = killarr_section

    for index in sorted(instance_data.keys()):
        data = instance_data[index].copy()
        name = data.pop('name', '')
        if name:
            if name in config['instances']:
                raise ValueError(f"Duplicate instance name '{name}' found at index {index}.")
            data.setdefault('enabled', True)
            config['instances'][name] = data
        else:
            _LOGGER.warning(f'Skipping unconfigured instance slot at index {index} (name is empty).')

    return parse_config(config)


def parse_config(config: Any) -> dict:
    """Validate a loaded configuration dictionary.

    Reads the optional ``killarr:`` section for global settings, falling back
    to schema defaults when the section is absent (shared rangarr config).
    Reads ``instances:`` for connection details, grouping enabled instances
    by arr type.

    Args:
        config: The parsed configuration object (from YAML or env vars).

    Returns:
        Validated and normalized configuration dictionary.

    Raises:
        ValueError: If required keys are missing or values are invalid.
    """
    if not isinstance(config, dict):
        raise ValueError('Configuration file must be a YAML mapping at the top level.')

    for key in REQUIRED_TOP_LEVEL:
        if key not in config:
            raise ValueError(f"Missing required top-level key: '{key}'")

    killarr_section = config.get('killarr', {})
    if not isinstance(killarr_section, dict):
        raise ValueError("'killarr' must be a YAML mapping.")

    settings = dict(killarr_section)
    validate_global_settings(settings, SETTINGS_SCHEMA)
    validate_stall_action_settings(settings)
    config['global_settings'] = settings

    raw_instances = config.get('instances', {})
    if not isinstance(raw_instances, dict):
        raise ValueError("'instances' must be a YAML mapping.")

    final_instances: dict[str, list] = {'radarr': [], 'sonarr': [], 'lidarr': []}
    all_empty = True

    for instance_name, instance_config in raw_instances.items():
        if not isinstance(instance_config, dict):
            raise ValueError(f"Instance '{instance_name}' must be a YAML mapping.")
        parsed = _parse_instance(instance_name, instance_config)
        if parsed is not None:
            inst_type, inst = parsed
            all_empty = False
            final_instances[inst_type].append(inst)

    if all_empty:
        raise ValueError("No instances defined under 'instances'. Add at least one Radarr, Sonarr, or Lidarr instance.")

    config['instances'] = final_instances
    return config
