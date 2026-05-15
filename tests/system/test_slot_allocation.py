"""Tests for killarr _allocate_slots weighted round-robin logic."""

# pylint: disable=protected-access
from typing import Any
from unittest.mock import MagicMock

import pytest

from killarr.main import _allocate_slots


def _make_client_with_weight(name: str, weight: float = 1.0) -> MagicMock:
    """Create a minimal mock client with name and weight set."""
    client = MagicMock()
    client.name = name
    client.weight = weight
    return client


_allocate_slots_cases = {
    'limit_zero_returns_empty': {
        'limit': 0,
        'backlogs': {'a': ['i1', 'i2']},
        'expected_count': 0,
    },
    'empty_backlogs_returns_empty': {
        'limit': 10,
        'backlogs': {},
        'expected_count': 0,
    },
    'single_client_respects_limit': {
        'limit': 2,
        'backlogs': {'a': ['i1', 'i2', 'i3']},
        'expected_count': 2,
    },
    'unlimited_returns_all': {
        'limit': -1,
        'backlogs': {'a': ['i1', 'i2', 'i3']},
        'expected_count': 3,
    },
}


@pytest.mark.parametrize(
    'limit, backlogs, expected_count',
    [(case['limit'], case['backlogs'], case['expected_count']) for case in _allocate_slots_cases.values()],
    ids=list(_allocate_slots_cases.keys()),
)
def test_allocate_slots_basic(limit: Any, backlogs: Any, expected_count: Any) -> None:
    """Test basic _allocate_slots behaviour for limits and empty inputs."""
    clients = {_make_client_with_weight(k): v for k, v in backlogs.items()}
    result = _allocate_slots(limit, clients)
    assert len(result) == expected_count


def test_allocate_slots_round_robins_two_clients() -> None:
    """Test that _allocate_slots alternates items between two equal-weight clients."""
    ca = _make_client_with_weight('A', weight=1.0)
    cb = _make_client_with_weight('B', weight=1.0)
    result = _allocate_slots(4, {ca: ['a1', 'a2'], cb: ['b1', 'b2']})
    clients_in_order = [r[0] for r in result]
    # With equal weight, should alternate: A B A B (or B A B A)
    assert clients_in_order[0] != clients_in_order[1]
    assert clients_in_order[1] != clients_in_order[2]
    assert clients_in_order[2] != clients_in_order[3]


def test_allocate_slots_higher_weight_gets_more_turns() -> None:
    """Test that a client with weight=2 gets twice as many items per round as weight=1."""
    ca = _make_client_with_weight('A', weight=2.0)
    cb = _make_client_with_weight('B', weight=1.0)
    result = _allocate_slots(6, {ca: ['a1', 'a2', 'a3', 'a4'], cb: ['b1', 'b2']})
    a_count = sum(1 for client, _ in result if client is ca)
    b_count = sum(1 for client, _ in result if client is cb)
    assert a_count == 4
    assert b_count == 2


def test_allocate_slots_exhausted_backlog_continues_other_clients() -> None:
    """Test that when one client runs out of items, remaining slots go to others."""
    ca = _make_client_with_weight('A', weight=1.0)
    cb = _make_client_with_weight('B', weight=1.0)
    result = _allocate_slots(5, {ca: ['a1'], cb: ['b1', 'b2', 'b3', 'b4']})
    assert len(result) == 5
    a_count = sum(1 for client, _ in result if client is ca)
    b_count = sum(1 for client, _ in result if client is cb)
    assert a_count == 1
    assert b_count == 4


def test_allocate_slots_stops_mid_turn_when_limit_hit() -> None:
    """Test that _allocate_slots stops mid-turn when the limit is reached during a weighted client's turn."""
    ca = _make_client_with_weight('A', weight=2.0)
    result = _allocate_slots(1, {ca: ['a1', 'a2', 'a3']})
    assert len(result) == 1
    assert result[0][0] is ca
    assert result[0][1] == 'a1'
