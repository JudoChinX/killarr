"""Tests for killarr StallClassifier."""

import pytest

from killarr.classifier import classify

_classify_cases = {
    'no_upgrade': (['Not a Custom Format upgrade for existing movie file(s)'], 'no_upgrade'),
    'no_upgrade_do_not_improve': (['do not improve on Existing file quality'], 'no_upgrade'),
    'manual_import': (['Manual Import required'], 'manual_import'),
    'manual_import_by_id': (['matched to movie by id'], 'manual_import'),
    'manual_import_series_by_id': (
        ['release was matched to series by ID. Automatic import is not possible.'],
        'manual_import',
    ),
    'manual_import_single_episode_file': (
        ['Single episode file contains all episodes in seasons. Review file name or manually import'],
        'manual_import',
    ),
    'no_files': (['No files found are eligible for import'], 'no_files'),
    'missing_items': (['not imported or missing from the release'], 'missing_items'),
    'missing_items_not_found_in_release': (
        ['Episode 2x01 was not found in the grabbed release: Show.S02'],
        'missing_items',
    ),
    'tba_title': (['Episode has a TBA title'], 'tba_title'),
    'unknown_fallback': (['Some unrecognised warning message'], 'unknown'),
    'empty_messages': ([], 'no_messages'),
    'multiple_messages_first_match_wins': (
        ['Some unknown warning', 'Not a Custom Format upgrade for existing movie file(s)'],
        'no_upgrade',
    ),
}


@pytest.mark.parametrize(
    'messages, expected',
    _classify_cases.values(),
    ids=list(_classify_cases.keys()),
)
def test_classify(messages: list[str], expected: str) -> None:
    """Test that classify maps message strings to the correct stall category."""
    assert classify(messages) == expected
