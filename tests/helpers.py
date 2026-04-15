"""Shared test helpers for killarr test suite."""

from typing import Any
from unittest.mock import MagicMock


def assert_config_result(result: Any, expected: Any) -> None:
    """Assert that a parsed config result matches all expected keys and values.

    Args:
        result: The parsed configuration dictionary returned by a config loader.
        expected: A partial dictionary of expected keys and values to assert against.

    Raises:
        AssertionError: If any expected key or value does not match the result.
    """
    for key, value in expected.items():
        if key == 'global_settings':
            for setting_key, setting_value in value.items():
                assert result['global_settings'][setting_key] == setting_value
        elif key == 'instances':
            for arr_type, instances_list in value.items():
                assert len(result['instances'][arr_type]) >= len(instances_list)
                for index, expected_instance in enumerate(instances_list):
                    for instance_key, instance_value in expected_instance.items():
                        assert result['instances'][arr_type][index][instance_key] == instance_value
        else:
            raise AssertionError(f"Unknown expected key: '{key}'")


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
