# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
