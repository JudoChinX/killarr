<p align="center">
  <img src="https://github.com/JudoChinX/unraid-templates/raw/main/assets/killarr-logo.png" alt="Killarr Logo" width="256">
</p>

<p align="center">
  <a href="https://github.com/JudoChinX/killarr/actions/workflows/ci.yml">
    <img src="https://github.com/JudoChinX/killarr/actions/workflows/ci.yml/badge.svg" alt="Tests & Quality">
  </a>
  <a href="https://github.com/JudoChinX/killarr/releases">
    <img src="https://img.shields.io/github/v/release/JudoChinX/killarr" alt="GitHub Release">
  </a>
  <a href="https://hub.docker.com/r/judochinx/killarr">
    <img src="https://img.shields.io/docker/pulls/judochinx/killarr" alt="Docker Pulls">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.13+-blue.svg" alt="Python 3.13+">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff">
  </a>
  <a href="https://github.com/pylint-dev/pylint">
    <img src="https://img.shields.io/badge/linting-pylint-yellowgreen" alt="pylint">
  </a>
  <a href="https://mypy-lang.org">
    <img src="https://img.shields.io/badge/type%20checked-mypy-blue" alt="mypy">
  </a>
  <a href="https://github.com/adrienverge/yamllint">
    <img src="https://img.shields.io/badge/yamllint-enabled-blue" alt="yamllint">
  </a>
  <a href="https://github.com/PyCQA/bandit">
    <img src="https://img.shields.io/badge/security-bandit-yellow.svg" alt="security: bandit">
  </a>
  <a href="https://pytest.org">
    <img src="https://img.shields.io/badge/tested%20with-pytest-0a9edc" alt="pytest">
  </a>
  <a href="https://hub.docker.com/r/judochinx/killarr/tags">
    <img src="https://img.shields.io/badge/arch-amd64%20%7C%20arm64-blue" alt="Architectures">
  </a>
  <a href="https://github.com/sponsors/JudoChinX">
    <img src="https://img.shields.io/badge/Sponsor-JudoChinX-ea4aaa?logo=github-sponsors" alt="Sponsor">
  </a>
  <a href="https://github.com/JudoChinX/rangarr">
    <img src="https://img.shields.io/badge/pairs%20with-Rangarr-blue" alt="Pairs with Rangarr">
  </a>
</p>

**Killarr** is a lightweight service that detects and removes stalled downloads from Radarr, Readarr, Sonarr, Lidarr, and Whisparr queues. It runs on a configurable schedule, finds items stuck with a warning status, removes them from the queue, and optionally triggers a fresh search.

## Key Features

- **Stall Detection:** Identifies downloads stuck in a warning state via `trackedDownloadStatus`.
- **Stall Classification:** Inspects `statusMessages` to categorise each stall into one of nine categories: `no_upgrade`, `manual_import`, `no_files`, `missing_items`, `tba_title`, `dangerous_file`, `generic`, `no_messages`, or `unknown`.
- **Granular Stall Actions:** Assign `remove`, `blocklist`, and `search` flags per stall category — globally or per instance — for precise control over each stall type.
- **Batch Size Controls:** Limit removals per cycle (`0` = disabled, `-1` = unlimited, `N` = global cap across all instances).
- **Weighted Round-Robin Allocation:** Distribute the batch budget across instances by weight; interleave items from different instances or drain one at a time.
- **Removal Ordering:** Process stalled items in API order, oldest-first, newest-first, A→Z, Z→A, or random order via `removal_order`.
- **Active Hours:** Restrict removal cycles to a configured time window (e.g. `06:00-23:00`). Overnight windows are supported.
- **Per-Media Cooldown:** Skip re-actioning the same media within a configurable interval (`retry_interval_minutes`) to avoid churn when replacements stall immediately.
- **Tag Filtering:** Include or exclude items based on tags set in your \*arr instances.
- **Startup Verification:** Unreachable instances are retried and then skipped, rather than crashing the service.
- **Detailed Logging:** Cycle summaries with evaluation counts, removal ETAs, and granular skip reasons (DEBUG level).
- **Dry Run Mode:** Log what would be removed without making any changes.
- **Shared Config with [Rangarr](https://github.com/JudoChinX/rangarr):** Killarr reads the same `instances:` section as Rangarr. Both tools can share a single `config.yaml` — no duplication required.

## Why Killarr?

The \*arr ecosystem is fantastic, but stalled downloads are a recurring friction point. Whether it's a release with no seeders, a "sample-only" file that confuses the importer, or a download that simply won't finish, these items clutter your activity queue and prevent successful grabs of alternative releases.

Killarr acts as an automated cleanup crew. By identifying these stuck items and removing them (with an optional automatic search for a replacement), it keeps your library growing without manual intervention.

## Documentation

- **[User Guide](docs/user-guide.md)** — Setup, configuration, Docker networking, shared config with [Rangarr](https://github.com/JudoChinX/rangarr), and troubleshooting.
- **[Technical Audit](docs/technical-audit.md)** — Architecture, security model, and design philosophy.
- **[Style Guide](docs/style-guide.md)** — Coding standards and contribution guidelines.

## Quick Start (Docker Compose)

The fastest way to get started is with Docker Compose.

1.  **Download example files:**
    ```bash
    curl -O https://raw.githubusercontent.com/JudoChinX/killarr/main/config.example.yaml
    curl -O https://raw.githubusercontent.com/JudoChinX/killarr/main/compose.example.yaml
    mv config.example.yaml config.yaml
    mv compose.example.yaml compose.yaml
    ```
2.  **Configure:** Edit `config.yaml` with your \*arr API keys and URLs.
3.  **Deploy:**
    ```bash
    docker compose up -d
    ```

## Minimal Configuration

```yaml
killarr:
  interval: 3600    # Run every hour
  dry_run: true     # Start in dry run mode — no removals until you're satisfied
  default:
    remove: true
    blocklist: true
    search: true
  no_upgrade: {}      # Leave custom-format blocks alone (no action)

instances:
  Radarr:
    type: radarr
    host: "http://radarr:7878"
    api_key: "YOUR_RADARR_API_KEY"
    enabled: true
```

See [config.example.yaml](config.example.yaml) for a full reference including tag filtering and per-instance overrides.

## Related Projects

- **[Rangarr](https://github.com/JudoChinX/rangarr)** — Automates and staggers media searches across Radarr, Sonarr, and Lidarr. Shares the same `config.yaml` format as Killarr — both tools can run side-by-side from a single config file.

## Development Transparency

AI tooling was used to assist with development tasks in this project. The architecture — no database, no persistence layer, five files, two dependencies — was designed by the author. All code is human-reviewed before inclusion.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) and the [Style Guide](docs/style-guide.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
