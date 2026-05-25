# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Readarr (`readarr`) as a supported instance type, using the v1 API. Titles are formatted as `'{authorName} - {bookTitle}'`.
- `fetch_page_size` setting (default: `500`, min: `1`): controls the page size for *arr queue API requests. Higher values reduce round trips for large queues at the cost of a longer per-request time.
- Whisparr v2 (`whisparr_v2`) and Whisparr v3 (`whisparr_v3`) as supported instance types. Whisparr v2 is Sonarr-based; Whisparr v3 is Radarr-based. The bare `whisparr` type is accepted as an alias for `whisparr_v3`.

### Fixed

- Queue fetches now include unknown items (downloads not linked to a media entry) by passing `includeUnknownMovieItems`, `includeUnknownSeriesItems`, and `includeUnknownAlbumItems` to the respective arr APIs. Stalled unknown items were previously invisible to killarr and would never be removed.
- `_get_media_id` no longer raises `KeyError` when processing unknown queue items whose media ID field is absent. Such items receive a media ID of `0`.


## [0.0.7] - 2026-05-21

### Changed

- Unsupported instance types (e.g. an unrecognized `type:` value) now log an error and skip the instance rather than aborting startup.


## [0.0.6] - 2026-05-16

### Breaking Changes

- The `stalled` config key has been renamed to `generic`. Rename any `stalled:` entries in your config to `generic:`. (#25)
- The `generic` key no longer acts as the universal fallback. If you relied on `generic:` to catch all unset categories, add a `default:` key with the same flags alongside it. (#26)

### Changed

- The `generic` category now classifies transient stall patterns exclusively (locked by another process, qBittorrent downloading metadata, no seeders). (#25)
- Introduced `default` as the universal stall action fallback. All unset categories — including `generic` — fall back to `default`. This separates classification (`generic`) from fallback configuration (`default`). (#26)

### Fixed

- Explicit empty dicts (e.g. `no_upgrade: {}`) now correctly produce `ignore` and do not inherit the fallback. (#25)


## [0.0.5] - 2026-05-16

### Breaking Changes

- Stall action config values have changed from strings (`remove`, `blocklist`, `retry`, `ignore`) to granular boolean flags. Replace each action string with explicit flags — e.g. `blocklist` becomes `remove: true` + `blocklist: true` + `search: true`.

### Changed

- Replace string stall actions with granular remove/blocklist/search flags.


## [0.0.4] - 2026-05-13

### Added

- `removal_order` setting: control the order in which stalled items are processed within a cycle (`api_order`, `age_ascending`, `age_descending`).
- `interleave_instances` setting: when `true`, items from different instances alternate in the removal queue rather than draining one instance at a time.
- `weight` per-instance setting: priority multiplier for weighted round-robin slot allocation across the global `batch_size` budget.
- `retry_interval_minutes` setting: per-media cooldown — skip re-actioning the same media ID within the configured interval to avoid churn when replacements stall immediately.
- `active_hours` setting: restrict removal cycles to a configured time window (`HH:MM-HH:MM`). Overnight windows are supported. Outside the window, Killarr sleeps until the window opens.
- Startup connection verification: each configured instance is tested at startup with configurable retries. Instances that fail to connect are skipped rather than crashing the service.


## [0.0.3] - 2026-04-28

### Changed

- Detailed logging: added skip reasons, cycle summaries with evaluation counts and removal ETAs, and enhanced startup diagnostics.


## [0.0.2] - 2026-04-25

### Added

- Update stall cause classifications based on arr source code. (#5)
- Add Rangarr badge to README. (#4)
- Add related projects to README. (#3)

### Changed

- Improve logging and deduplicate stall messages. (#6)


## [0.0.1] - 2026-04-25

### Added

- Queue fetch with client-side stall filtering (`trackedDownloadStatus == "warning"`)
- Stall reason classification: inspects `statusMessages` to categorise stalls (e.g., `no_upgrade`, `manual_import`, `missing_items`)
- Named action dispatch: assign `ignore`, `remove`, `retry`, or `blocklist` actions per stall category (resolves globally or per instance)
- Batch size controls: `0` (disabled), `-1` (unlimited), `N > 0` (limit removals per cycle)
- `stagger_interval_seconds`: wait between individual removal operations
- Tag filtering via `include_tags` and `exclude_tags` (resolved from *arr instances at startup)
- Dry run mode: log what would be removed without making any changes
- Environment variable config mode (`KILLARR_CONFIG_SOURCE=env`) with `KILLARR_GLOBAL_*` and `KILLARR_INSTANCE_<n>_*` variables
- `KILLARR_INSTANCE_SOURCE=shared`: when set, Killarr reads `RANGARR_INSTANCE_*` environment variables for instance definitions instead of `KILLARR_INSTANCE_*`, mirroring the shared `config.yaml` experience for env-var deployments
- Shared config format: reads `killarr:` + `instances:` sections; compatible with Rangarr's `global:` + `instances:` layout in the same file
- Per-instance `killarr:` overrides: any global setting can be overridden per instance
- Radarr support (v3 API endpoints: `/api/v3/queue`, `/api/v3/command`)
- Sonarr support (v3 API endpoints: `/api/v3/queue`, `/api/v3/command`)
- Lidarr support (v1 API endpoints: `/api/v1/queue`, `/api/v1/command`)
- Multi-stage distroless Docker image (`gcr.io/distroless/python3-debian13`) running as `nonroot` (UID 65532)
- Comprehensive test suite (159 tests) with 99% coverage
