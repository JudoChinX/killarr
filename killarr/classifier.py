"""Stall reason classifier for *arr queue items."""

_PATTERNS: tuple[tuple[str, str], ...] = (
    # --- Shared Patterns ---
    ('potentially dangerous file extension', 'dangerous_file'),
    ('import failed, path does not exist', 'manual_import'),
    ('non-sample file detected', 'manual_import'),
    ('not enough space', 'manual_import'),
    ('sample file detected', 'manual_import'),
    ('no audio files found', 'no_files'),
    ('no files found are eligible for import', 'no_files'),
    ('no video files found', 'no_files'),
    ('already meets cutoff', 'no_upgrade'),
    ('custom format upgrade', 'no_upgrade'),
    ('do not improve on existing', 'no_upgrade'),
    ('not a custom format upgrade', 'no_upgrade'),
    ('not an upgrade for existing', 'no_upgrade'),
    ('is locked by another process', 'stalled'),
    ('qbittorrent is downloading metadata', 'stalled'),
    ('the download is stalled with no', 'stalled'),
    # --- Radarr Specific ---
    ('found matching movie via grab history', 'manual_import'),
    ('release was matched to movie by id', 'manual_import'),
    ('matched to movie by id', 'manual_import'),
    ('unable to determine if file is a sample', 'manual_import'),
    ('not imported or missing from the release', 'missing_items'),
    # --- Sonarr Specific ---
    ('automatic import is not possible', 'manual_import'),
    ("release title doesn't match series title", 'manual_import'),
    ('release was matched to series by id', 'manual_import'),
    ('matched to series by id', 'manual_import'),
    ('single episode file contains all episodes', 'manual_import'),
    ('single episode file contains', 'manual_import'),
    ('not found in the grabbed release', 'missing_items'),
    ('tba title', 'tba_title'),
    # --- Lidarr Specific ---
    ('matched to album by id', 'manual_import'),
    ('track does not belong to album', 'manual_import'),
    # --- Fallbacks (Generic strings must be last) ---
    ('manual import required', 'manual_import'),
)


def classify(messages: list[str]) -> str:
    """Classify *arr status messages into a stall category.

    Args:
        messages: List of status message strings from a queue record's statusMessages.

    Returns:
        One of 'no_upgrade', 'manual_import', 'no_files', 'missing_items', 'tba_title',
        'stalled', 'no_messages', 'dangerous_file', or 'unknown'.
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
