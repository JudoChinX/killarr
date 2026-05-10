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

Killarr is a ~883-line Python service with four core modules:

```
killarr/
├── main.py           # Entry point and run loop
├── classifier.py     # Stall reason classification logic
├── config_parser.py  # Configuration loading and validation
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
4. Resolve the named action (`ignore`, `remove`, `retry`, `blocklist`) based on configuration
5. Apply tag filtering (include/exclude) and batch size limits
6. DELETE each stalled item (with optional `removeFromClient` and `blocklist` params)
7. POST a search command for each removed item (if action is `retry` or `blocklist`)
8. Sleep for `interval` seconds and repeat

---

## Module Breakdown

### main.py — Entry Point and Run Loop

**Purpose:** Loads configuration, instantiates clients, and runs the removal cycle on a schedule.

**Key Functions:**
- `run()`: Loads configuration (file or env), builds clients, starts the infinite loop.
- `_run_removal_cycle()`: Calls `get_stalled_items()` on each client and `execute_removal()` for any found.
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

### clients/arr.py — \*arr API Client

**Purpose:** Implements all \*arr API interactions for queue management.

**Classes:**
- `ArrClient`: Abstract base class with queue fetching, stall filtering, removal, and search-again logic.
- `RadarrClient`: Radarr-specific implementation (v3 endpoints, `movieId`, `MoviesSearch` command).
- `SonarrClient`: Sonarr-specific implementation (v3 endpoints, `episodeId`, `EpisodeSearch` command).
- `LidarrClient`: Lidarr-specific implementation (v1 endpoints, `albumId`, `AlbumSearch` command).

**Key Methods:**
- `get_stalled_items()`: Fetches the full queue, filters for stalled items, classifies them via `classifier.py`, and applies tag filtering and batch limits. Returns a tuple of `(actionable_items, skip_stats)` where `skip_stats` is a dictionary of evaluation and skip counts.
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
| `/api/v3/queue` (Radarr/Sonarr), `/api/v1/queue` (Lidarr) | GET | Fetch all queue records | Per cycle per instance | Read-only |
| `/api/v3/queue/{id}` (Radarr/Sonarr), `/api/v1/queue/{id}` (Lidarr) | DELETE | Remove stalled queue item | Per stalled item | **Write** |
| `/api/v3/command` (Radarr/Sonarr), `/api/v1/command` (Lidarr) | POST | Trigger fresh search | Per removal (if action is `retry` or `blocklist`) | **Write** |
| `/api/v3/tag` (Radarr/Sonarr), `/api/v1/tag` (Lidarr) | GET | Resolve tag names to IDs | Startup only (if tags configured) | Read-only |

**Search Commands Sent:**
- Radarr: `{"name": "MoviesSearch", "movieIds": [<id>]}`
- Sonarr: `{"name": "EpisodeSearch", "episodeIds": [<id>]}`
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
def _remove_single(self, queue_id, media_id, title, action, index, total):
    if self.dry_run:
        _LOGGER.info(f'[{self.name}] [DRY RUN] Would {action}: {title}')
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

**Decision:** ~883 lines of core Python code, zero external dependencies beyond `requests` and `PyYAML`.

**Why:** Small codebases are auditable. Every line of code is a potential attack surface. By keeping the codebase minimal, security reviewers can read and understand the entire project in under an hour.

**Trade-off:** Some convenience features are intentionally omitted to maintain this simplicity.

### 2. Explicit Over Implicit

**Decision:** No magic, no auto-discovery, no background services you didn't configure.

**Why:** Security incidents often stem from software doing things users don't expect. Every API call Killarr makes is explicitly listed in this document. Every configuration option must be set by the user.

### 3. Write-Light

**Decision:** Only two write operations exist — DELETE queue items and POST search commands.

**Why:** Write operations are where damage can happen. Killarr cannot modify your library, change settings, or access download clients. Both write operations match actions you would take manually in the \*arr UI, and both can be disabled by setting actions to `ignore` or using `dry_run: true`.

### 4. Test Coverage as Documentation

**Decision:** 159 tests covering all code paths including error conditions.

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

**Test Coverage:** 159 tests, 99.37% coverage.

- `tests/test_config_parser.py`: Configuration validation, schema defaults, shared config, env var mode — no network calls.
- `tests/test_arr_client.py`: Queue fetch, stall filtering, removal, search-again, tag resolution, dry run, stagger — all with mocked HTTP responses.
- `tests/test_classifier.py`: Stall reason classification tests — no network calls.
- `tests/test_main.py`: Run loop, cycle orchestration, client building, config loading — mocked clients and config paths.
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

- `killarr/main.py`: 184 lines
- `killarr/classifier.py`: 41 lines
- `killarr/config_parser.py`: 333 lines
- `killarr/clients/arr.py`: 323 lines
- `killarr/__init__.py`: 1 line (package marker)
- `killarr/clients/__init__.py`: 1 line (package marker)
- **Total:** ~883 lines of Python

The small codebase size makes comprehensive security auditing feasible.

---

## Verification

Don't trust documentation — verify the claims:

1. **Run the tests:** `pytest` — see that security-relevant code is tested.
2. **Read the code:** Start with `killarr/main.py` — 184 lines.
3. **Check the API calls:** Enable `LOG_LEVEL=DEBUG` — every HTTP request and detailed skip reasons are logged.
4. **Observe the cycle:** Look for cycle summaries in the logs (`Found X items to remove (Evaluated: Y, Skipped: Z)`) to confirm operation.
5. **Review dependencies:** `cat requirements.txt` — two libraries, both standard.

If anything in this document contradicts the code, the code is correct and this document needs updating. File an issue.
