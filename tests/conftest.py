"""Global fixtures for the killarr test suite."""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def block_external_requests() -> Generator[None, None, None]:
    """Ensure no real HTTP requests are made during tests."""
    with patch('requests.Session.request', side_effect=RuntimeError('Unintended external network access!')):
        yield


@pytest.fixture(autouse=True)
def mock_sleep() -> Generator[None, None, None]:
    """Block real sleeping in tests for speed and determinism."""
    with patch('time.sleep'):
        yield
