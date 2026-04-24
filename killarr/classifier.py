"""Stall reason classifier for *arr queue items."""

_PATTERNS: tuple[tuple[str, str], ...] = (
    # Shared
    ('custom format upgrade', 'no_upgrade'),
    ('do not improve on existing', 'no_upgrade'),
    ('manual import required', 'manual_import'),
    ('no files found are eligible for import', 'no_files'),
    # Radarr
    ('matched to movie by id', 'manual_import'),
    ('not imported or missing from the release', 'missing_items'),
    # Sonarr
    ('matched to series by id', 'manual_import'),
    ('automatic import is not possible', 'manual_import'),
    ('single episode file contains', 'manual_import'),
    ('not found in the grabbed release', 'missing_items'),
    ('tba title', 'tba_title'),
)


def classify(messages: list[str]) -> str:
    """Classify *arr status messages into a stall category.

    Args:
        messages: List of status message strings from a queue record's statusMessages.

    Returns:
        One of 'no_upgrade', 'manual_import', 'no_files', 'missing_items', 'tba_title',
        'stalled', 'no_messages', or 'unknown'.
    """
    if not messages:
        return 'no_messages'

    combined = ' '.join(messages).lower()
    category = 'unknown'
    for pattern, cat in _PATTERNS:
        if pattern in combined:
            category = cat
            break

    return category
