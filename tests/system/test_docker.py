"""E2E system tests using real Docker instances of Radarr, Readarr, Sonarr, Lidarr, and Whisparr."""

# pylint: disable=protected-access,redefined-outer-name
import logging
import os
import socket
import sqlite3
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Generator

import pytest
import requests

from killarr.main import _run_removal_cycle
from killarr.main import build_arr_clients

logger = logging.getLogger(__name__)

_COMPOSE_NETWORK: str = 'killarr-test-net'
_COMPOSE_PATH: str = os.path.join(os.path.dirname(__file__), 'compose.yaml')

_API_VERSIONS: dict[str, str] = {
    'lidarr': 'v1',
    'radarr': 'v3',
    'readarr': 'v1',
    'sonarr': 'v3',
    'whisparr_v2': 'v3',
    'whisparr_v3': 'v3',
}

_CONTAINER_NAMES: dict[str, str] = {
    'lidarr': 'killarr-test-lidarr',
    'radarr': 'killarr-test-radarr',
    'readarr': 'killarr-test-readarr',
    'sonarr': 'killarr-test-sonarr',
    'whisparr_v2': 'killarr-test-whisparr-v2',
    'whisparr_v3': 'killarr-test-whisparr-v3',
}

_DB_PATHS: dict[str, str] = {
    'lidarr': '/config/lidarr.db',
    'radarr': '/config/radarr.db',
    'readarr': '/config/readarr.db',
    'sonarr': '/config/sonarr.db',
    'whisparr_v2': '/config/whisparr2.db',
    'whisparr_v3': '/config/whisparr3.db',
}

_HTTP_TIMEOUT: int = 10

_SERVICES: dict[str, int] = {
    'lidarr': 8686,
    'radarr': 7878,
    'readarr': 8787,
    'sonarr': 8989,
    'whisparr_v2': 6969,
    'whisparr_v3': 6969,
}


def _container_url(container_name: str, port: int) -> str:
    """Return the base URL for a container using its Docker network IP."""
    res = subprocess.run(
        ['docker', 'inspect', '-f', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', container_name],
        capture_output=True,
        text=True,
        check=True,
    )
    return f'http://{res.stdout.strip()}:{port}'


def _extract_api_key(container_name: str) -> str:
    """Extract the API key from a container's /config/config.xml."""
    result = subprocess.run(
        ['docker', 'exec', container_name, 'cat', '/config/config.xml'],
        capture_output=True,
        text=True,
        check=True,
    )
    tree = ET.fromstring(result.stdout)
    api_key = tree.findtext('ApiKey')
    assert api_key, f'No ApiKey found in {container_name} config.xml'
    return api_key


def _trigger_monitoring(url: str, api_key: str, api_version: str) -> None:
    """Best-effort: POST RefreshMonitoredDownloads so arr checks the download client immediately."""
    logger.info('Triggering monitoring refresh for %s.', url)
    try:
        requests.post(
            f'{url}/api/{api_version}/command',
            json={'name': 'RefreshMonitoredDownloads'},
            headers={'X-Api-Key': api_key},
            timeout=5,
        )
    except requests.RequestException:
        pass


def _wait_for_ping(url: str, timeout: int = 120) -> None:
    """Poll /ping until the service responds, raising TimeoutError on failure."""
    logger.info('Waiting for %s to become healthy...', url)
    for _ in range(timeout):
        try:
            resp = requests.get(f'{url}/ping', timeout=5)
            if resp.ok:
                logger.info('%s is healthy.', url)
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise TimeoutError(f'Service at {url} did not become healthy within {timeout}s')


def _wait_for_stalled_item(url: str, api_key: str, api_version: str, timeout: int = 60) -> None:
    """Poll the arr queue until a stalled item appears, raising TimeoutError on failure."""
    logger.info('Waiting for stalled item to appear in %s queue...', url)
    for _ in range(timeout):
        try:
            resp = requests.get(
                f'{url}/api/{api_version}/queue',
                headers={'X-Api-Key': api_key},
                params={
                    'includeUnknownAlbumItems': 'true',
                    'includeUnknownBookItems': 'true',
                    'includeUnknownMovieItems': 'true',
                    'includeUnknownSeriesItems': 'true',
                },
                timeout=5,
            )
            if resp.ok and any(r.get('trackedDownloadStatus') == 'warning' for r in resp.json().get('records', [])):
                logger.info('%s stalled item detected in queue.', url)
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise TimeoutError(f'No stalled item appeared in queue at {url} within {timeout}s')


@pytest.fixture(scope='session')
def api_keys(docker_env: dict[str, str]) -> dict[str, str]:
    """Extract API keys from all running Arr containers."""
    return {service: _extract_api_key(_CONTAINER_NAMES[service]) for service in docker_env}


# Override autouse fixtures from tests/conftest.py so Docker tests are not
# subject to network blocking or time pinning.
@pytest.fixture(autouse=True)
def block_network() -> None:  # type: ignore[override]
    """No-op: Docker tests manage their own network."""


@pytest.fixture(scope='session')
def docker_env() -> Generator[dict[str, str], None, None]:
    """Start Docker Arr containers and yield a mapping of service name to base URL."""
    subprocess.run(
        ['docker', 'compose', '-f', _COMPOSE_PATH, 'down', '--volumes', '--remove-orphans'],
        capture_output=True,
        check=False,
    )
    logger.info('Starting compose stack...')
    result = subprocess.run(
        ['docker', 'compose', '-f', _COMPOSE_PATH, 'up', '-d', '--wait', '--build'],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f'docker compose up failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}')
    logger.info('Compose stack up. Connecting runner to network %s...', _COMPOSE_NETWORK)
    subprocess.run(
        ['docker', 'network', 'connect', _COMPOSE_NETWORK, socket.gethostname()],
        capture_output=True,
        check=False,
    )

    urls: dict[str, str] = {
        service: _container_url(_CONTAINER_NAMES[service], port) for service, port in _SERVICES.items()
    }

    yield urls

    logger.info('Tearing down compose stack...')
    subprocess.run(
        ['docker', 'network', 'disconnect', _COMPOSE_NETWORK, socket.gethostname()],
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ['docker', 'compose', '-f', _COMPOSE_PATH, 'down'],
        check=True,
    )


@pytest.fixture(autouse=True)
def pin_time() -> None:  # type: ignore[override]
    """No-op: Docker tests use real time."""


@pytest.fixture(scope='session')
def seeded_env(docker_env: dict[str, str], api_keys: dict[str, str]) -> None:
    """Seed each arr's SQLite database and wait for stalled items to appear in the queue."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
    for service in docker_env:
        logger.info('Seeding %s database...', service)
        container = _CONTAINER_NAMES[service]
        db_path = _DB_PATHS[service]
        sql_path = os.path.join(fixtures_dir, service, 'seed.sql')

        subprocess.run(['docker', 'stop', container], check=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            host_db = os.path.join(tmpdir, 'app.db')
            subprocess.run(['docker', 'cp', f'{container}:{db_path}', host_db], check=True)
            for ext in ('-wal', '-shm'):
                subprocess.run(
                    ['docker', 'cp', f'{container}:{db_path}{ext}', f'{host_db}{ext}'],
                    capture_output=True,
                    check=False,
                )
            conn = sqlite3.connect(host_db)
            try:
                with open(sql_path, encoding='utf-8') as sql_file:
                    conn.executescript(sql_file.read())
                conn.commit()
                conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                conn.commit()
            finally:
                conn.close()
            os.chmod(host_db, 0o666)
            subprocess.run(['docker', 'cp', host_db, f'{container}:{db_path}'], check=True)
            for ext in ('-wal', '-shm'):
                wal_path = f'{host_db}{ext}'
                if os.path.exists(wal_path):
                    subprocess.run(
                        ['docker', 'cp', wal_path, f'{container}:{db_path}{ext}'],
                        check=True,
                    )

        subprocess.run(['docker', 'start', container], check=True)
        new_url = _container_url(container, _SERVICES[service])
        docker_env[service] = new_url
        _wait_for_ping(new_url)
        subprocess.run(['docker', 'exec', container, 'mkdir', '-p', '/tmp/media'], check=True)
        # FakeSAB returns items as Completed with a storage path. The path must exist
        # (even if empty) so arr sets trackedDownloadStatus=warning ("No files found")
        # rather than silently waiting for the path to become available.
        service_cap = service.capitalize()
        subprocess.run(
            ['docker', 'exec', container, 'mkdir', '-p', f'/downloads/complete/{service}/Test.{service_cap}.Media'],
            check=True,
        )

        # Trigger monitoring so arr re-scans FakeSAB and creates TrackedDownloads
        # with trackedDownloadStatus=warning for killarr to act on.
        _trigger_monitoring(new_url, api_keys[service], _API_VERSIONS[service])
        _wait_for_stalled_item(new_url, api_keys[service], _API_VERSIONS[service], timeout=120)
    logger.info('All services seeded and restarted.')


def test_api_connectivity(docker_env: dict[str, str], api_keys: dict[str, str]) -> None:
    """Verify API key auth works against each arr's system/status endpoint."""
    for service, url in docker_env.items():
        ver = _API_VERSIONS[service]
        resp = requests.get(
            f'{url}/api/{ver}/system/status',
            headers={'X-Api-Key': api_keys[service]},
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        assert 'version' in data
        logger.info('%s API OK (version: %s).', service, data.get('version', 'unknown'))


def test_containers_healthy(docker_env: dict[str, str]) -> None:
    """Verify all Arr containers respond to /ping."""
    for service, url in docker_env.items():
        resp = requests.get(f'{url}/ping', timeout=_HTTP_TIMEOUT)
        assert resp.ok, f'{service} ping failed'
        logger.info('%s ping OK.', service)


def test_removal_cycle_clears_stalled_items(
    docker_env: dict[str, str],
    api_keys: dict[str, str],
    seeded_env: None,  # pylint: disable=unused-argument
) -> None:
    """_run_removal_cycle removes stalled queue items from each arr instance."""
    instances_config = {
        service: [{'name': f'docker-{service}', 'url': url, 'api_key': api_keys[service], 'weight': 1.0}]
        for service, url in docker_env.items()
    }
    global_settings = {
        'dry_run': False,
        'batch_size': -1,
        'stagger_interval_seconds': 0,
        'retry_interval_minutes': 0,
        'default': {'remove': True, 'blocklist': False, 'search': False},
    }
    clients = build_arr_clients(instances_config, global_settings)
    logger.info('Running removal cycle against %d service(s).', len(docker_env))
    _run_removal_cycle(clients, global_settings)

    for service, url in docker_env.items():
        ver = _API_VERSIONS[service]
        resp = requests.get(
            f'{url}/api/{ver}/queue',
            headers={'X-Api-Key': api_keys[service]},
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        stalled = [r for r in resp.json().get('records', []) if r.get('trackedDownloadStatus') == 'warning']
        assert not stalled, f'{service} still has {len(stalled)} stalled item(s) after removal cycle'
        logger.info('%s queue clear.', service)
