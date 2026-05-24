"""Minimal SABnzbd HTTP mock for killarr Docker system tests."""

import json
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from typing import override
from urllib.parse import parse_qs
from urllib.parse import urlparse

_DOWNLOAD_IDS: dict[str, str] = {
    'lidarr': 'killarr-test-lidarr-001',
    'radarr': 'killarr-test-radarr-001',
    'sonarr': 'killarr-test-sonarr-001',
    'whisparr_v2': 'killarr-test-whisparr-v2-001',
    'whisparr_v3': 'killarr-test-whisparr-v3-001',
}

# Items live in history as Completed. The arr instance tries to import from the
# storage path; the path exists but holds no eligible media files, so arr leaves
# the item in the queue with trackedDownloadStatus=warning. killarr then removes it.
_active_ids: set[str] = set(_DOWNLOAD_IDS.values())


def _make_history_slot(arr_type: str, download_id: str) -> dict:
    """Build a SABnzbd history slot dict for the given arr type and download ID."""
    return {
        'status': 'Completed',
        'nzo_id': download_id,
        'name': f'Test.{arr_type.capitalize()}.Media',
        'category': arr_type,
        'storage': f'/downloads/complete/{arr_type}/Test.{arr_type.capitalize()}.Media',
        'size': 1073741824,
        'nzb_name': f'Test.{arr_type.capitalize()}.Media.nzb',
        'download_time': 60,
        'stage_log': [],
        'fail_message': '',
        'action_line': '',
        'script_line': '',
        'script_log': '',
        'loaded': False,
    }


class _Handler(BaseHTTPRequestHandler):
    @override
    def do_GET(self) -> None:  # pylint: disable=invalid-name,missing-function-docstring
        params = parse_qs(urlparse(self.path).query)
        mode = params.get('mode', [''])[0]

        if mode == 'version':
            data: dict = {'version': '3.7.0'}
        elif mode == 'queue':
            if params.get('name', [''])[0] == 'delete':
                nzo_id = params.get('value', [''])[0]
                _active_ids.discard(nzo_id)
                data = {'status': True, 'nzo_ids': [nzo_id]}
            else:
                data = {
                    'queue': {
                        'status': 'Idle',
                        'speed': '0 B/s',
                        'slots': [],
                        'noofslots': 0,
                        'paused': False,
                    }
                }
        elif mode == 'history':
            if params.get('name', [''])[0] == 'delete':
                nzo_id = params.get('value', [''])[0]
                _active_ids.discard(nzo_id)
                data = {'status': True}
            else:
                slots = [
                    _make_history_slot(arr_type, did) for arr_type, did in _DOWNLOAD_IDS.items() if did in _active_ids
                ]
                data = {'history': {'slots': slots, 'noofslots': len(slots)}}
        elif mode == 'get_config':
            data = {
                'config': {
                    'misc': {
                        'enable_ratings': False,
                        'download_dir': '/downloads/incomplete',
                        'complete_dir': '/downloads/complete',
                        'host': '0.0.0.0',
                        'port': 8080,
                        'sanitize_safe': False,
                        'folder_rename': True,
                        'replace_spaces': False,
                        'replace_dots': False,
                        'extra_par2_pct': 0,
                        'extra_par2_limit': 0,
                        'auto_sort': '',
                        'sort_files': False,
                        'nice': '',
                        'ionice': '',
                        'enable_tv_sorting': False,
                        'enable_movie_sorting': False,
                        'enable_date_sorting': False,
                    },
                    'categories': [
                        {'name': '*', 'order': 0, 'dir': '', 'newzbin': '', 'pp': '', 'script': 'None', 'priority': 0},
                        {
                            'name': 'radarr',
                            'order': 1,
                            'dir': 'radarr',
                            'newzbin': '',
                            'pp': '',
                            'script': 'None',
                            'priority': 0,
                        },
                        {
                            'name': 'sonarr',
                            'order': 2,
                            'dir': 'sonarr',
                            'newzbin': '',
                            'pp': '',
                            'script': 'None',
                            'priority': 0,
                        },
                        {
                            'name': 'lidarr',
                            'order': 3,
                            'dir': 'lidarr',
                            'newzbin': '',
                            'pp': '',
                            'script': 'None',
                            'priority': 0,
                        },
                        {
                            'name': 'whisparr_v2',
                            'order': 4,
                            'dir': 'whisparr_v2',
                            'newzbin': '',
                            'pp': '',
                            'script': 'None',
                            'priority': 0,
                        },
                        {
                            'name': 'whisparr_v3',
                            'order': 5,
                            'dir': 'whisparr_v3',
                            'newzbin': '',
                            'pp': '',
                            'script': 'None',
                            'priority': 0,
                        },
                    ],
                    'servers': [],
                }
            }
        else:
            data = {'status': True}

        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @override
    def log_message(self, fmt: str, *args: object) -> None:  # pylint: disable=missing-function-docstring
        pass


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8080), _Handler)
    server.serve_forever()
