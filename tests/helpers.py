"""Shared test helpers for killarr test suite."""

from typing import Any
from unittest.mock import MagicMock


def mock_http_response(data: Any = None) -> MagicMock:
    """Return a mock HTTP response with raise_for_status and json()."""
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = data
    return mock


def mock_queue_response(records: list[dict]) -> MagicMock:
    """Return a mock HTTP response shaped like the arr queue API."""
    return mock_http_response({
        'records': records,
        'totalRecords': len(records),
        'page': 1,
        'pageSize': 100,
    })


def mock_tag_response(tags: list[dict]) -> MagicMock:
    """Return a mock HTTP response shaped like the arr tag API."""
    return mock_http_response(tags)
