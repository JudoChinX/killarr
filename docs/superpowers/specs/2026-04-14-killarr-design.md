# Killarr Design Spec

**Date:** 2026-04-14
**Status:** Approved

## Overview

Killarr is a lightweight orchestration service that automatically removes stalled downloads from *arr application queues (Radarr, Sonarr, Lidarr). It is intentionally modeled on [rangarr](https://github.com/JudoChinX/rangarr) — same structure, same toolchain, same philosophy — with the action changed from triggering searches to removing stalled queue items.

A stalled item is defined as any queue entry the arr app itself has flagged with `trackedDownloadStatus == "warning"`. Killarr does not implement its own staleness detection.

## Architecture & File Layout

```
killarr/
├── killarr/
│   ├── __init__.py
│   ├── main.py          # Entry point, run loop, cycle orchestration
│   ├── config_parser.py # YAML + env var config loading/validation
│   └── clients/
│       ├── __init__.py
│       └── arr.py       # ArrClient base + Lidarr/Radarr/Sonarr subclasses
├── tests/
│   ├── builders.py
│   ├── helpers.py
│   ├── test_arr_client.py
│   ├── test_config_parser.py
│   └── test_main.py
├── docs/
├── Dockerfile
├── pyproject.toml
├── config.example.yaml
└── compose.example.yaml
```

**Toolchain:** Python 3.13+, uv, ruff, pylint, mypy, bandit, pytest (≥95% coverage). Docker multi-stage build using distroless base, running as nonroot. Identical to rangarr in every respect.

**App support:** Radarr, Sonarr, Lidarr. Additional apps added as rangarr adds them.

## Shared Configuration

Killarr can share a `config.yaml` with rangarr. The `instances:` section (host, api_key, type, enabled) is shared between both tools. Each tool reads its own top-level section and ignores the other's.

```yaml
global:                         # rangarr reads this, killarr ignores
  interval: 3600
  missing_batch_size: 20

killarr:                        # killarr reads this, rangarr ignores
  interval: 3600
  stagger_interval_seconds: 5
  batch_size: 10
  remove_from_client: true
  blocklist: true
  search_again: true
  dry_run: false

instances:                      # both tools read this for connection details
  radarr:
    type: radarr
    host: "http://radarr:7878"
    api_key: "YOUR_KEY"
    enabled: true
    killarr:                    # instance-level killarr overrides (optional)
      batch_size: 5
      blocklist: false

  sonarr:
    type: sonarr
    host: "http://sonarr:8989"
    api_key: "YOUR_KEY"
    enabled: true

  lidarr:
    type: lidarr
    host: "http://lidarr:8686"
    api_key: "YOUR_KEY"
    enabled: false
```

Rangarr's config parser already silently ignores unknown top-level keys, so the `killarr:` section does not break it. Killarr mounts the same config volume in Docker.

### Settings Schema

| Setting | Default | Description |
|---|---|---|
| `interval` | `3600` | Seconds between cycles |
| `stagger_interval_seconds` | `5` | Seconds between individual removals |
| `batch_size` | `10` | Max stalled items to remove per cycle (0=disabled, -1=unlimited) |
| `remove_from_client` | `true` | Delete from download client on removal |
| `blocklist` | `true` | Blocklist the release on removal |
| `search_again` | `true` | Trigger a fresh search after removal |
| `dry_run` | `false` | Log what would happen without making changes |
| `include_tags` | `[]` | Only act on items with ANY of these tags |
| `exclude_tags` | `[]` | Skip items with ANY of these tags |

All settings can be overridden per-instance under `instances.<name>.killarr:`. If no `killarr:` top-level section exists (e.g. a rangarr-only config), killarr falls back to all defaults gracefully.

Config source is controlled via `KILLARR_CONFIG_SOURCE=file|env` (mirrors rangarr's `RANGARR_CONFIG_SOURCE`). Environment variable config follows the same `KILLARR_INSTANCE_0_*` pattern as rangarr.

## Core Logic & Data Flow

Each cycle iterates over all active clients:

1. **Fetch stalled queue items** — `GET /api/v3/queue` (paginated). The arr API does not support server-side filtering by status, so killarr fetches all queue records and filters client-side to those where `trackedDownloadStatus == "warning"`. Batch size controls max items acted on after filtering.
2. **Apply tag filtering** — same `include_tags`/`exclude_tags` logic as rangarr, resolved via `GET /api/v3/tag` at startup.
3. **Remove each item** with stagger between:
   - `DELETE /api/v3/queue/{id}?removeFromClient={bool}&blocklist={bool}`
   - If `search_again=true`: `POST /api/v3/command` with the media's search command
4. **Log** each action in rangarr's format: `[InstanceName] Removed (stalled): Title (1/5)`

### ArrClient Abstracts

Carries over `_command_name` and `_id_field` from rangarr unchanged (needed for the search-again POST). Adds one new abstract:

- `_get_media_id(record: dict) -> int` — extracts the movie/series/album ID from a queue record for the follow-up search command. Queue record structure differs slightly per app.

Lidarr overrides all endpoints to `/api/v1/...` as in rangarr.

### Per-App Search Commands

| App | `_command_name` | `_id_field` |
|---|---|---|
| Radarr | `MoviesSearch` | `movieIds` |
| Sonarr | `EpisodeSearch` | `episodeIds` |
| Lidarr | `AlbumSearch` | `albumIds` |

Dry run mode logs what would be removed/searched without making any API calls.

## Error Handling

| Scenario | Behavior |
|---|---|
| Network failure on queue fetch | Log error, skip instance this cycle, continue with others |
| Failed DELETE | Log error with title and ID, continue with remaining items |
| Failed search-again POST | Log warning (removal already succeeded, do not retry) |
| Invalid config at startup | Log error and `sys.exit(1)` |
| Unknown tag name in include/exclude | Log warning, ignore that tag |
| No `killarr:` section in config | Fall back to all defaults, log info message |

## Testing

pytest at ≥95% coverage. Test structure mirrors rangarr:

- `tests/builders.py` — factory helpers for queue record fixtures
- `tests/helpers.py` — shared utilities
- `tests/test_arr_client.py` — unit tests for queue fetch, tag filtering, removal logic
- `tests/test_config_parser.py` — config loading, validation, env var expansion, shared-config parsing
- `tests/test_main.py` — cycle orchestration, startup, dry run

Key test cases unique to killarr:
- Stalled item detected → DELETE called with correct query params
- `remove_from_client: false` → `removeFromClient` param absent from DELETE
- `search_again: false` → no POST to command endpoint
- `blocklist: false` → `blocklist` param absent from DELETE
- Instance-level `killarr:` override takes precedence over global `killarr:` settings
- Config with no `killarr:` section → all defaults applied, no error
- Rangarr config loaded by killarr → instances parsed correctly, `global:` section ignored
