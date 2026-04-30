"""Tests for killarr StallClassifier."""

import pytest

from killarr.classifier import classify

_classify_cases = {
    'no_upgrade': (['Not a Custom Format upgrade for existing movie file(s)'], 'no_upgrade'),
    'no_upgrade_do_not_improve': (['do not improve on Existing file quality'], 'no_upgrade'),
    'already_meets_cutoff': (['Quality for release in queue already meets cutoff: Bluray-1080p v1'], 'no_upgrade'),
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
    'no_video_files': (['No video files found'], 'no_files'),
    'no_audio_files': (['No audio files found'], 'no_files'),
    'missing_items': (['not imported or missing from the release'], 'missing_items'),
    'missing_items_not_found_in_release': (
        ['Episode 2x01 was not found in the grabbed release: Show.S02'],
        'missing_items',
    ),
    'tba_title': (['Episode has a TBA title'], 'tba_title'),
    'qbit_metadata': (['qBittorrent is downloading metadata'], 'stalled'),
    'dangerous_ext': (['Potentially dangerous file extension: .exe'], 'dangerous_file'),
    'not_an_upgrade': (['Not an upgrade for existing movie file(s)'], 'no_upgrade'),
    'path_not_exist': (['Import failed, path does not exist'], 'manual_import'),
    'radarr_id_match': (['Release was matched to movie by ID'], 'manual_import'),
    'sonarr_title_mismatch': (["Release title doesn't match series title"], 'manual_import'),
    'sonarr_id_match': (['Release was matched to series by ID'], 'manual_import'),
    'sonarr_multi_episode': (['Single episode file contains all episodes'], 'manual_import'),
    'manual_import_sample': (['Unable to determine if file is a sample'], 'manual_import'),
    'manual_import_sample_detected': (['Sample file detected'], 'manual_import'),
    'manual_import_non_sample': (['Non-sample file detected'], 'manual_import'),
    'stalled_no_connections': (['The download is stalled with no connections'], 'stalled'),
    'stalled_no_peers': (['The download is stalled with no peers'], 'stalled'),
    'stalled_locked': (['File is locked by another process'], 'stalled'),
    'manual_import_no_space': (['Not enough space'], 'manual_import'),
    'lidarr_album_mismatch': (['Track does not belong to album'], 'manual_import'),
    'lidarr_id_match': (['Matched to album by ID'], 'manual_import'),
    'manual_import_grab_history': (
        ['Found matching movie via grab history, but release was matched to movie by ID. Manual Import required'],
        'manual_import',
    ),
    'unknown_fallback': (['Some unrecognized warning message'], 'unknown'),
    'empty_messages': ([], 'no_messages'),
    'multiple_messages_first_match_wins': (
        ['Not an upgrade for existing movie file(s)', 'Manual Import required'],
        'manual_import',
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
