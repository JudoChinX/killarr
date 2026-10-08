# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-08

### Added

- `fetch_timeout` setting (default `30` seconds, minimum `1`) controlling how long to wait for each page of the queue response. It can be set globally or per instance. Raise it for instances with very large queues where the previous hardcoded 30-second limit was exceeded. Tag lookups, connection checks, queue deletes, and search commands continue to use a fixed 15-second timeout.
- `dead_download` stall category for downloads that are dead in the download client but never reach a stalled status in the *arr app, such as an NZBGet post-process that failed with `Mark Status: BAD`. A queue record is a candidate when its `trackedDownloadStatus` is `ok`, its `trackedDownloadState` is `downloading`, and either `sizeleft` is `0` or the download client `status` is `warning`. The record's `errorMessage` is included in the stall details.
- `dead_download_minutes` setting (default `360` minutes, minimum `0`) controlling how long a record must stay a dead-download candidate before it is classified as `dead_download`. Set it to `0` to disable dead-download detection. It can be set globally or per instance. Candidates still inside the grace period appear as `Dead pending: N` in the cycle summary.

### Changed

- An existing `default` action now also applies to dead downloads once they pass the `dead_download_minutes` grace period. To keep dead downloads in the queue while `default` handles other categories, set `dead_download: {}`.
- The run `interval` is now measured from the start of one cycle to the start of the next. Previously the full interval was slept after each cycle finished, so long cycles (large batches with a stagger) pushed every subsequent cycle later. The cycle-complete log line now reports the actual seconds until the next cycle.
- The startup registration line now shows the resolved client type and weight, for example `Registered WhisparrV3 instance: Whisparr (Weight: 1)`. Failed queue removals and search commands now include the first 300 characters of the *arr response body in the log, flattened to a single line with any echoed API key redacted, which makes API-side rejections diagnosable.

### Fixed

- Boolean values are no longer accepted for integer settings or for an instance's `weight`. Previously a value like `batch_size: true` was silently treated as `1` instead of being rejected.
- Per-instance `killarr:` overrides are now validated at startup, including on disabled instances, the same as the top-level `killarr:` section. Previously an invalid override such as `batch_size: "lots"` or a stall category set to a string passed configuration validation and surfaced later as a runtime error, in the worst case crashing mid-cycle. Error messages name the instance, for example `'instances.Radarr-4K.killarr.batch_size' must be of type int.`
- Active hours no longer spams the log when less than one second remains before the window opens. The seconds-until-open calculation now rounds up instead of truncating, so at least one second is always slept.
- Corrected an off-by-one error in the removal ETA. The ETA now reflects `N - 1` stagger intervals for `N` items, matching actual sleep behavior. Single-item batches no longer display an ETA.

## [0.1.0] - 2026-05-25

### Added

- Readarr (`readarr`) as a supported instance type, using the v1 API. Titles are formatted as `'{authorName} - {bookTitle}'`.
- `fetch_page_size` setting (default: `500`, min: `1`): controls the page size for *arr queue API requests. Higher values reduce round trips for large queues at the cost of a longer per-request time.
- `removal_order` now accepts `alphabetical_ascending`, `alphabetical_descending`, and `random` in addition to the existing `api_order`, `age_ascending`, and `age_descending` values. `random` is useful when `batch_size` limits removals per cycle and you want to spread removal pressure across the backlog rather than always processing the same items.
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
- Stall reason classification: inspects `statusMessages` to categorize stalls (e.g., `no_upgrade`, `manual_import`, `missing_items`)
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
