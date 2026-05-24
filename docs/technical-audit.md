# Technical Audit

Architecture, security model, and design philosophy for Killarr. Intended for security reviewers, contributors, and anyone who wants to verify the software's claims.

---

## Table of Contents

- [Why This Project Exists](#why-this-project-exists)
- [What Killarr Does NOT Do](#what-killarr-does-not-do)
- [Architecture Overview](#architecture-overview)
- [Module Breakdown](#module-breakdown)
- [API Interactions](#api-interactions)
- [Client-Side Filtering Rationale](#client-side-filtering-rationale)
- [Security-Critical Code Paths](#security-critical-code-paths)
- [Design Principles](#design-principles)
- [Technical Decisions](#technical-decisions)
- [Testing Strategy](#testing-strategy)
- [Dependencies](#dependencies)
- [File Sizes](#file-sizes)
- [Verification](#verification)

---

## Why This Project Exists

Stalled downloads are a recurring pain point in \*arr setups. Items can get stuck in the queue indefinitely — the download client reports a warning status, but nothing clears them automatically. The common workarounds (manual intervention, Radarr/Sonarr's built-in "remove" + "search again") require periodic attention.

Killarr automates this. It runs on a schedule, finds stalled items, classifies the stall reason, and performs automated cleanup based on configurable actions. It is a companion to [Rangarr](https://github.com/JudoChinX/rangarr) and shares the same trust-first philosophy: small codebase, no external connections, everything auditable.

---

## What Killarr Does NOT Do

To be absolutely clear, Killarr does not and will never:

- Access media files on disk
- Connect to external services (indexers, trackers, notification services, etc.)
- Collect usage statistics or telemetry
- Phone home or check for updates
- Modify \*arr configuration settings or quality profiles
- Add or remove media from your library
- Access download client APIs or credentials directly
- Access user authentication data beyond API keys

---

## Architecture Overview

Killarr is a ~1,403-line Python service with five core modules:

```
killarr/
├── main.py           # Entry point and run loop
├── classifier.py     # Stall reason classification logic
├── config_parser.py  # Configuration loading and validation
├── validators.py     # Schema constants and validation functions
└── clients/
    └── arr.py        # *arr API client implementations
```

**Data Flow:**
```
config.yaml → config_parser.py → main.py → ArrClient instances → classifier.py → *arr APIs
```

Each cycle:
1. Fetch the full queue from each \*arr instance (paginated)
2. Filter client-side for `trackedDownloadStatus == "warning"`
3. Pass status messages to `classifier.py` to categorise the stall reason
4. Resolve action flags (`remove`, `blocklist`, `search`) for each stall category based on configuration
5. Apply tag filtering (include/exclude) and batch size limits
6. Sort actionable items by `removal_order` setting (`api_order`, `age_ascending`, `age_descending`)
7. DELETE each stalled item (with optional `removeFromClient` and `blocklist` params)
8. POST a search command for each removed item (if `search: true`)
9. Sleep for `interval` seconds and repeat

---

## Module Breakdown

### main.py — Entry Point and Run Loop

**Purpose:** Loads configuration, instantiates clients, and runs the removal cycle on a schedule.

**Key Functions:**
- `run()`: Loads configuration (file or env), builds clients, starts the infinite loop.
- `_run_removal_cycle()`: Collects stalled items from each client, sorts them via `_apply_removal_order()`, allocates removal slots via `_allocate_slots()`, and calls `execute_removal()` per item.
- `_allocate_slots()`: Distributes the global batch limit across clients using weighted round-robin allocation.
- `_apply_removal_order()`: Sorts each client's backlog in-place by the `removal_order` setting before slot allocation.
- `build_arr_clients()`: Instantiates \*arr clients from the parsed config, merging global settings with per-instance overrides.
- `_load_config_from_paths()`: Tries each config file path in order, returning the first successfully loaded config.
- `_get_setting()`: Helper to read a setting with fallback to the schema default.

**No direct network activity:** Only calls client methods; does not make HTTP requests directly.

### classifier.py — Stall Reason Classification

**Purpose:** Maps \*arr status messages to stall categories.

**Key Functions:**
- `classify()`: Takes a list of messages and returns a category string (e.g., `no_upgrade`, `manual_import`, `missing_items`).

**No network activity:** Pure string matching logic.

### config_parser.py — Configuration Loading and Validation

**Purpose:** Loads and validates YAML or environment variable configuration.

**Key Functions:**
- `load_config()`: Reads `config.yaml` from disk, expands `${VAR}` placeholders, delegates to `parse_config()`.
- `load_config_from_env()`: Reads `KILLARR_GLOBAL_*` and `KILLARR_INSTANCE_<n>_*` environment variables, constructs an equivalent config dict, delegates to `parse_config()`.
- `parse_config()`: Validates and normalises the loaded configuration: applies schema defaults, validates types and ranges, groups enabled instances by type.
- `_parse_instance()`: Validates each instance entry, renames `host` to `url` for internal use, extracts and promotes per-instance `killarr:` overrides.

**No network activity:** Pure configuration parsing; never makes HTTP requests.

**Security note:** API keys are extracted from config and passed to client instances. Keys are never logged.

### validators.py — Schema Constants and Validation

**Purpose:** Defines `SETTINGS_SCHEMA` and `STALL_CATEGORIES`, and implements all validation logic for configuration values.

**Key Functions:**
- `validate_global_settings()`: Applies defaults and validates all settings against their schema definitions.
- `validate_stall_action_settings()`: Validates any stall category action values present in settings.

**No network activity:** Pure validation logic.

### clients/arr.py — \*arr API Client

**Purpose:** Implements all \*arr API interactions for queue management.

**Classes:**
- `ArrClient`: Abstract base class with queue fetching, stall filtering, removal, and search-again logic.
- `RadarrClient`: Radarr-specific implementation (v3 endpoints, `movieId`, `MoviesSearch` command).
- `ReadarrClient`: Readarr-specific implementation (v1 endpoints, `bookId`, `BookSearch` command).
- `SonarrClient`: Sonarr-specific implementation (v3 endpoints, `episodeId`, `EpisodeSearch` command).
- `LidarrClient`: Lidarr-specific implementation (v1 endpoints, `albumId`, `AlbumSearch` command).
- `WhisparrV2Client`: Whisparr v2 implementation, inherits `SonarrClient` (Sonarr-based API, `episodeId`, `EpisodeSearch`).
- `WhisparrV3Client`: Whisparr v3 implementation, inherits `RadarrClient` (Radarr-based API, `movieId`, `MoviesSearch`).

**Key Methods:**
- `get_stalled_items()`: Fetches the full queue, filters for stalled items, classifies them via `classifier.py`, and applies tag filtering and batch limits. Returns a tuple of `(actionable_items, skip_stats)` where each `QueueItem` carries `queue_id`, `media_id`, `title`, `remove`, `blocklist`, `search`, `category`, `messages`, and `added` (ISO 8601 timestamp from the \*arr API).
- `_fetch_all_queue()`: Paginates through the \*arr queue endpoint until all records are retrieved.
- `_is_stalled()`: Returns `True` if `trackedDownloadStatus == "warning"`.
- `execute_removal()`: Removes a single queue item by delegating to `_remove_single()`.
- `_trigger_search()`: POSTs a search command to the \*arr command endpoint.
- `_resolve_tag_ids()`: At startup, fetches all tags from the instance and resolves configured tag names to IDs.

**Security note:** This is the ONLY module that makes network requests. All API calls use the session configured in `__init__` with `X-Api-Key` header.

---

## API Interactions

| Endpoint | Method | Purpose | Frequency | Read/Write |
|---|---|---|---|---|
| `/api/v3/queue` (Radarr/Sonarr/Whisparr), `/api/v1/queue` (Lidarr/Readarr) | GET | Fetch all queue records | Per cycle per instance | Read-only |
| `/api/v3/queue/{id}` (Radarr/Sonarr/Whisparr), `/api/v1/queue/{id}` (Lidarr/Readarr) | DELETE | Remove stalled queue item | Per stalled item | **Write** |
| `/api/v3/command` (Radarr/Sonarr/Whisparr), `/api/v1/command` (Lidarr/Readarr) | POST | Trigger fresh search | Per removal (if action is `retry` or `blocklist`) | **Write** |
| `/api/v3/tag` (Radarr/Sonarr/Whisparr), `/api/v1/tag` (Lidarr/Readarr) | GET | Resolve tag names to IDs | Startup only (if tags configured) | Read-only |

**Search Commands Sent:**
- Radarr / Whisparr v3: `{"name": "MoviesSearch", "movieIds": [<id>]}`
- Readarr: `{"name": "BookSearch", "bookIds": [<id>]}`
- Sonarr / Whisparr v2: `{"name": "EpisodeSearch", "episodeIds": [<id>]}`
- Lidarr: `{"name": "AlbumSearch", "albumIds": [<id>]}`

**Data Accessed:**
- Queue metadata only: titles, IDs, download status, status messages
- No media files, no user data, no download client information

---

## Client-Side Filtering Rationale

The \*arr queue API (`GET /api/v3/queue`) does not expose `trackedDownloadStatus` as a server-side filter parameter. Killarr fetches all queue pages and applies the `trackedDownloadStatus == "warning"` filter locally.

This is an intentional architectural decision. The alternative — relying on a server-side filter that may not exist or behave consistently across \*arr versions — would make the filtering less transparent and harder to test. Client-side filtering means the logic is entirely visible in the source, fully unit-tested, and immune to API inconsistencies between Radarr, Sonarr, and Lidarr versions.

The trade-off is that Killarr fetches the full queue each cycle rather than a pre-filtered subset. For typical homelab queue sizes (tens to low hundreds of items), this is negligible.

---

## Security-Critical Code Paths

### API Key Usage

**Location:** `clients/arr.py` — `ArrClient.__init__`

API keys are set once during client initialization:
```python
self.session.headers.update({'X-Api-Key': api_key, 'Content-Type': 'application/json'})
```

This is the ONLY place API keys are used. They are:
- Never logged
- Never transmitted except in the `X-Api-Key` header to your configured instances
- Never stored to disk
- Only held in memory during service runtime

### Write Operations

**Location:** `clients/arr.py` — `ArrClient._remove_single()` and `ArrClient._trigger_search()`

DELETE and POST requests are the only write operations. Both are guarded by the `dry_run` check:

```python
def _remove_single(self, item: QueueItem, index: int, total: int) -> None:
    parts = ['remove']
    if item.blocklist:
        parts.append('blocklist')
    if item.search:
        parts.append('search')
    action_label = '+'.join(parts)
    if self.dry_run:
        _LOGGER.info(f'[{self.name}] [DRY RUN] Would {action_label} ({item.category}): {item.title} ({index}/{total})')
        return
    # ... DELETE request
```

When `dry_run: true`, no network write operations are made.

### Network Activity

Killarr operates entirely within your local network:
- Only communicates with URLs explicitly configured in `config.yaml`
- No telemetry, analytics, or external API calls
- No automatic updates or version checks

---

## Design Principles

### 1. Security Through Simplicity

**Decision:** ~1,403 lines of core Python code, zero external dependencies beyond `requests` and `PyYAML`.

**Why:** Small codebases are auditable. Every line of code is a potential attack surface. By keeping the codebase minimal, security reviewers can read and understand the entire project in under an hour.

**Trade-off:** Some convenience features are intentionally omitted to maintain this simplicity.

### 2. Explicit Over Implicit

**Decision:** No magic, no auto-discovery, no background services you didn't configure.

**Why:** Security incidents often stem from software doing things users don't expect. Every API call Killarr makes is explicitly listed in this document. Every configuration option must be set by the user.

### 3. Write-Light

**Decision:** Only two write operations exist — DELETE queue items and POST search commands.

**Why:** Write operations are where damage can happen. Killarr cannot modify your library, change settings, or access download clients. Both write operations match actions you would take manually in the \*arr UI, and both can be disabled by setting actions to `ignore` or using `dry_run: true`.

### 4. Test Coverage as Documentation

**Decision:** 365 tests covering all code paths including error conditions.

**Why:** Tests serve three purposes:
1. Prevent regressions.
2. Document expected behaviour.
3. Prove security-relevant code works as claimed.

### 5. No Secrets in Code

**Decision:** All secrets live in `config.yaml` (gitignored). API keys never appear in logs.

**Why:** Credentials in code or logs are the most common source of credential leaks.

---

## Technical Decisions

### Distroless Container Image

**Choice:** `gcr.io/distroless/python3-debian13` as the runtime base image, built via a multi-stage Dockerfile.

**Why:** The runtime image contains only the Python interpreter, CA certificates, and the application itself. There is no shell, no package manager, no build tooling. This limits what an attacker can do with a compromised container.

**Trade-off:** Debugging a running container is harder — there is no shell to exec into. Use `LOG_LEVEL=DEBUG` and structured logs for diagnostics.

### Shared Config Format

**Choice:** Killarr reads a `killarr:` top-level key alongside the `instances:` key — the same structure Rangarr uses for its `global:` key.

**Why:** Users who already run Rangarr can add a `killarr:` section to their existing config file and start Killarr immediately. No duplicate instance definitions, no second config file to maintain. Users running Killarr alone can simply omit the `global:` key — Killarr ignores it.

### Client-Side Stall Filtering

**Choice:** Fetch the full queue and filter locally for `trackedDownloadStatus == "warning"`.

**Why:** The \*arr queue API does not expose this field as a server-side filter. Client-side filtering keeps the logic visible, testable, and consistent across all three \*arr applications. See [Client-Side Filtering Rationale](#client-side-filtering-rationale).

### Stateless Operation

**Choice:** No database, no persistent state between cycles.

**Why:** Nothing to corrupt, easy to restart, transparent behaviour. The \*arr queue itself is the source of truth — Killarr reads from it fresh each cycle.

### AI-Assisted Development

AI-assisted development tools were used to accelerate implementation, but not as a replacement for expertise.

**What AI helped with:** Boilerplate code generation, test case expansion, documentation consistency.

**What required human judgment:** Architecture decisions, security trade-offs, API design, test strategy.

Every line of AI-generated code was reviewed, tested, and validated against requirements.

---

## Testing Strategy

**Test Coverage:** 365 tests, 99.47% coverage.

- `tests/unit/test_config_parser.py`: Configuration validation, schema defaults, shared config, env var mode — no network calls.
- `tests/unit/test_validators.py`: Schema validation and setting constraints — no network calls.
- `tests/unit/test_classifier.py`: Stall reason classification tests — no network calls.
- `tests/integration/test_arr_client.py`: Queue fetch, stall filtering, removal, search-again, tag resolution, dry run, stagger — all with mocked HTTP responses.
- `tests/system/test_main.py`: Run loop, cycle orchestration, client building, config loading — mocked clients and config paths.
- `tests/system/test_slot_allocation.py`: Weighted slot allocation across instances — mocked clients.
- `tests/system/test_docker.py`: E2E system tests using real Docker instances of Radarr, Readarr, Sonarr, Lidarr, and Whisparr. Run separately in CI via the `docker_system_testing` job; excluded from the standard `pytest` run.
- `tests/builders.py`: Builder pattern for constructing queue record fixtures and client instances in tests.
- `tests/helpers.py`: Mock HTTP response factories for queue and tag endpoints.

**Testing Without Production Instances:**

1. **Dry Run Mode:** Set `dry_run: true` in config.yaml — no write operations are made.
2. **Debug Logging:** Set `LOG_LEVEL=DEBUG` — every queue item evaluated is logged.

---

## Dependencies

Runtime (see `requirements.txt`):
- `requests`: HTTP client for \*arr API calls.
- `PyYAML`: Configuration file parsing.

Both are widely-used, well-maintained libraries with public security disclosure policies.

Development (see `requirements-dev.txt`):
- `pytest`, `pytest-cov`: Test runner and coverage.
- `ruff`: Linting and formatting.
- `pylint`: Code quality analysis.
- `mypy`: Static type checking.
- `bandit`: Security vulnerability scanning.

---

## File Sizes

- `killarr/main.py`: 383 lines
- `killarr/classifier.py`: 87 lines
- `killarr/config_parser.py`: 266 lines
- `killarr/validators.py`: 185 lines
- `killarr/clients/arr.py`: 480 lines
- `killarr/__init__.py`: 1 line (package marker)
- `killarr/clients/__init__.py`: 1 line (package marker)
- **Total:** ~1,403 lines of Python

The small codebase size makes comprehensive security auditing feasible.

---

## Verification

Don't trust documentation — verify the claims:

1. **Run the tests:** `pytest` — see that security-relevant code is tested.
2. **Read the code:** Start with `killarr/main.py` — 383 lines.
3. **Check the API calls:** Enable `LOG_LEVEL=DEBUG` — every HTTP request and detailed skip reasons are logged.
4. **Observe the cycle:** Look for cycle summaries in the logs (`Found X items to remove (Evaluated: Y, Skipped: Z)`) to confirm operation.
5. **Review dependencies:** `cat requirements.txt` — two libraries, both standard.

If anything in this document contradicts the code, the code is correct and this document needs updating. File an issue.
