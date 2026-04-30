"""Stall reason classifier for *arr queue items."""

from enum import StrEnum


class StallCategory(StrEnum):
    """Enumeration of stall categories used to classify *arr queue items."""

    DANGEROUS_FILE = 'dangerous_file'
    MANUAL_IMPORT = 'manual_import'
    NO_FILES = 'no_files'
    NO_UPGRADE = 'no_upgrade'
    STALLED = 'stalled'
    MISSING_ITEMS = 'missing_items'
    TBA_TITLE = 'tba_title'
    NO_MESSAGES = 'no_messages'
    UNKNOWN = 'unknown'


_CATEGORY_MAP: dict[StallCategory, list[str]] = {
    StallCategory.DANGEROUS_FILE: [
        'potentially dangerous file extension',
    ],
    StallCategory.MANUAL_IMPORT: [
        'import failed, path does not exist',
        'non-sample file detected',
        'not enough space',
        'sample file detected',
        'found matching movie via grab history',
        'release was matched to movie by id',
        'matched to movie by id',
        'unable to determine if file is a sample',
        'automatic import is not possible',
        "release title doesn't match series title",
        'release was matched to series by id',
        'matched to series by id',
        'single episode file contains all episodes',
        'single episode file contains',
        'matched to album by id',
        'track does not belong to album',
        'manual import required',
    ],
    StallCategory.NO_FILES: [
        'no audio files found',
        'no files found are eligible for import',
        'no video files found',
    ],
    StallCategory.NO_UPGRADE: [
        'already meets cutoff',
        'custom format upgrade',
        'do not improve on existing',
        'not a custom format upgrade',
        'not an upgrade for existing',
    ],
    StallCategory.STALLED: [
        'is locked by another process',
        'qbittorrent is downloading metadata',
        'the download is stalled with no',
    ],
    StallCategory.MISSING_ITEMS: [
        'not imported or missing from the release',
        'not found in the grabbed release',
    ],
    StallCategory.TBA_TITLE: [
        'tba title',
    ],
}


def classify(messages: list[str]) -> str:
    """Classify *arr status messages into a stall category.

    Args:
        messages: List of status message strings from a queue record's statusMessages.

    Returns:
        One of 'no_upgrade', 'manual_import', 'no_files', 'missing_items', 'tba_title',
        'stalled', 'no_messages', 'dangerous_file', or 'unknown'.
    """
    if not messages:
        return str(StallCategory.NO_MESSAGES)

    combined = ' '.join(messages).lower()
    return next(
        (str(cat) for cat, patterns in _CATEGORY_MAP.items() if any(pattern in combined for pattern in patterns)),
        str(StallCategory.UNKNOWN),
    )
