"""Global fixtures for the killarr test suite."""

import datetime
import time

import pytest
import requests

FIXED_NOW = datetime.datetime(2026, 4, 23, 12, 0, 0, tzinfo=datetime.UTC)


class UnmockedNetworkError(Exception):
    """Raised when a test attempts an unmocked network call."""


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block all unmocked HTTP requests to prevent accidental network calls."""

    def mocked_request(*args: object, **kwargs: object) -> None:
        raise UnmockedNetworkError(f'Unmocked network call attempted: {args} {kwargs}')

    monkeypatch.setattr(requests.Session, 'request', mocked_request)


@pytest.fixture(autouse=True)
def pin_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin datetime.now() to a fixed value and suppress real sleeping."""

    class MockDatetime(datetime.datetime):
        """Datetime subclass with a pinned ``now()`` for deterministic tests."""

        @classmethod
        def now(cls, tz_info: datetime.tzinfo | None = None) -> datetime.datetime:  # type: ignore[override]  # pylint: disable=arguments-renamed
            return FIXED_NOW if tz_info is None else FIXED_NOW.astimezone(tz_info)

    monkeypatch.setattr(datetime, 'datetime', MockDatetime)
    monkeypatch.setattr(time, 'sleep', lambda secs: None)
