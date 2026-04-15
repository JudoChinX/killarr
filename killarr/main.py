"""Killarr entry point.

Orchestrates stalled download removal across multiple *arr instances by
fetching queue items, removing those in warning status, and repeating at
scheduled intervals.
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from killarr.clients.arr import ArrClient
from killarr.clients.arr import LidarrClient
from killarr.clients.arr import RadarrClient
from killarr.clients.arr import SonarrClient
from killarr.config_parser import SETTINGS_SCHEMA
from killarr.config_parser import get_setting_default
from killarr.config_parser import load_config
from killarr.config_parser import load_config_from_env

if 'TZ' not in os.environ:
    os.environ['TZ'] = 'UTC'
    if hasattr(time, 'tzset'):
        time.tzset()

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z',
    stream=sys.stdout,
)
logging.Formatter.converter = time.localtime
logger = logging.getLogger(__name__)

_CLIENT_MAP: dict[str, type[ArrClient]] = {
    'lidarr': LidarrClient,
    'radarr': RadarrClient,
    'sonarr': SonarrClient,
}


def _get_setting(settings: dict, key: str) -> Any:
    """Return setting value, falling back to its schema default."""
    return settings.get(key, get_setting_default(key))


def _load_config_from_paths(config_paths: list[str]) -> dict | None:
    """Attempt to load configuration from a list of possible file paths."""
    config = None
    error_message = None

    for config_path in config_paths:
        if Path(config_path).is_file():
            try:
                config = load_config(config_path)
                logger.info(f'Loaded configuration from: {config_path}')
                error_message = None
                break
            except ValueError as error:
                error_message = f'Configuration error in {config_path}: {error}'
                break
            except FileNotFoundError:
                continue

    if error_message:
        logger.error(error_message)
    elif config is None:
        logger.error(
            'No config.yaml found. Copy config.example.yaml to config.yaml and fill in your instance details.'
        )

    return config


def _log_killarr_start(active_clients: list[Any], settings: dict) -> None:
    """Log startup information."""
    batch = _get_setting(settings, 'batch_size')
    batch_str = {0: 'Disabled', -1: 'Unlimited'}.get(batch, str(batch))
    stagger = _get_setting(settings, 'stagger_interval_seconds')
    dry_run = _get_setting(settings, 'dry_run')
    dry_run_str = ' (DRY RUN ENABLED)' if dry_run else ''
    remove_str = 'yes' if _get_setting(settings, 'remove_from_client') else 'no'
    blocklist_str = 'yes' if _get_setting(settings, 'blocklist') else 'no'
    search_str = 'yes' if _get_setting(settings, 'search_again') else 'no'

    logger.info(
        f'Killarr started{dry_run_str} | '
        f'Instances: {len(active_clients)} active | '
        f'Run Interval: {_get_setting(settings, "interval")}s | '
        f'Batch: {batch_str} | '
        f'Stagger: {stagger}s | '
        f'Delete from client: {remove_str} | '
        f'Blocklist: {blocklist_str} | '
        f'Search again: {search_str}'
    )


def _run_removal_cycle(active_clients: list[Any], _settings: dict) -> None:
    """Run a single removal cycle across all active clients."""
    logger.info('--- Starting removal cycle ---')

    for client in active_clients:
        items = client.get_stalled_items()
        if not items:
            logger.info(f'[{client.name}] No stalled items found this cycle.')
            continue
        logger.info(f'[{client.name}] Found {len(items)} stalled item(s). Removing...')
        client.remove_stalled(items)


def build_arr_clients(
    instances_config: dict,
    settings: dict,
    client_registry: dict[str, type[ArrClient]] | None = None,
) -> list[ArrClient]:
    """Instantiate all *arr clients declared in the config.

    Args:
        instances_config: The ``instances`` section of the config dict.
        settings: The ``global_settings`` section of the config dict.
        client_registry: Optional client type registry (defaults to _CLIENT_MAP).

    Returns:
        Flat list of instantiated *arr client objects.
    """
    registry = client_registry if client_registry is not None else _CLIENT_MAP
    clients: list[ArrClient] = []
    for arr_type, client_class in registry.items():
        for instance in instances_config.get(arr_type, []):
            instance_overrides = {key: instance[key] for key in SETTINGS_SCHEMA if key in instance}
            client_settings = {**settings, **instance_overrides}
            client = client_class(
                name=instance['name'],
                url=instance['url'],
                api_key=instance['api_key'],
                settings=client_settings,
                weight=instance.get('weight', 1.0),
            )
            clients.append(client)
            logger.info(f'Registered {arr_type.capitalize()} instance: {instance["name"]}')
    return clients


def run() -> None:
    """Load configuration and start the removal loop."""
    config_source = os.environ.get('KILLARR_CONFIG_SOURCE', 'file').lower()
    if config_source == 'env':
        logger.info('Loading configuration from environment variables.')
        try:
            config = load_config_from_env()
        except ValueError as error:
            logger.error(f'Configuration error from environment: {error}')
            config = None
    else:
        if config_source != 'file':
            logger.warning(
                f"Unrecognized KILLARR_CONFIG_SOURCE value '{config_source}'. "
                "Expected 'file' or 'env'. Falling back to file mode."
            )
        config = _load_config_from_paths(['config/config.yaml', 'config.yaml'])

    if not config:
        sys.exit(1)

    settings = config.get('global_settings', {})
    active_clients = build_arr_clients(config.get('instances', {}), settings)

    if not active_clients:
        logger.warning("No *arr instances are configured. Add at least one entry under 'instances' to begin.")
        sys.exit(1)

    _log_killarr_start(active_clients, settings)

    run_interval_seconds = _get_setting(settings, 'interval')

    while True:
        _run_removal_cycle(active_clients, settings)
        logger.info(f'--- Cycle complete. Sleeping for {run_interval_seconds}s. ---')
        time.sleep(run_interval_seconds)


if __name__ == '__main__':
    run()
