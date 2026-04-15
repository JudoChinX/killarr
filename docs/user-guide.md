# User Guide

Complete guide to installing, configuring, and operating Killarr.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (Docker)](#quick-start-docker)
- [Configuration Sources](#configuration-sources)
- [Configuration Reference](#configuration-reference)
  - [Global Settings](#global-settings)
  - [Instance Settings](#instance-settings)
  - [Per-Instance Killarr Overrides](#per-instance-killarr-overrides)
  - [Environment Variable Expansion](#environment-variable-expansion)
  - [Environment Variable-Only Configuration](#environment-variable-only-configuration)
- [Shared Config with Rangarr](#shared-config-with-rangarr)
- [Docker](#docker)
  - [Docker Compose](#docker-compose)
  - [Docker Run](#docker-run)
  - [Docker Networking](#docker-networking)
- [Operational Best Practices](#operational-best-practices)
- [Troubleshooting](#troubleshooting)
- [Development Setup](#development-setup)

---

## Prerequisites

- **Docker** with Compose plugin (Docker Desktop or Docker Engine + Compose)

---

## Quick Start (Docker)

The fastest way to get Killarr running:

1. Download the example files:
   ```bash
   curl -O https://raw.githubusercontent.com/JudoChinX/killarr/main/config.example.yaml
   curl -O https://raw.githubusercontent.com/JudoChinX/killarr/main/compose.example.yaml
   mv config.example.yaml config.yaml
   mv compose.example.yaml compose.yaml
   chmod 644 config.yaml
   ```
   The `chmod 644` is required. The container runs as UID 65532 (`nonroot`), not your host user, so the file must be world-readable.

2. Edit `config.yaml` with your \*arr instance details.

3. Start the service with dry run enabled to verify your configuration before triggering real removals:
   ```yaml
   killarr:
     dry_run: true
   ```
   ```bash
   docker compose up -d && docker compose logs -f
   ```
   Confirm the log output looks correct, then set `dry_run: false` and restart.

4. Start normally:
   ```bash
   docker compose up -d
   ```

5. View logs:
   ```bash
   docker compose logs -f
   ```

---

## Configuration Sources

Killarr supports two primary configuration methods:
1. **YAML File (Default):** Configured via `config/config.yaml` (or `config.yaml` in the working directory).
2. **Environment Variables:** Configured via `KILLARR_GLOBAL_*` and `KILLARR_INSTANCE_*` variables.

To switch to environment-only configuration, set:
```bash
KILLARR_CONFIG_SOURCE=env
```

---

## Configuration Reference

Killarr is configured via a single `config.yaml` file under the `killarr:` top-level key.

### Configuration Structure

```yaml
killarr:
  # Global killarr settings

instances:
  Instance-Name:
    # Instance connection settings
    # killarr:   # Optional per-instance overrides
```

### Environment Variable Expansion

Any string value in `config.yaml` may contain `${VAR_NAME}` placeholders. Killarr replaces them with the matching environment variable at startup. Expansion applies to all string fields — not just `api_key`. A single value may contain multiple placeholders.

Set secrets as environment variables and reference them in `config.yaml`:

```yaml
# config.yaml
instances:
  Radarr:
    type: radarr
    host: "http://radarr:7878"
    api_key: ${RADARR_API_KEY}
    enabled: true
```

Pass the value via `compose.yaml`:

```yaml
environment:
  RADARR_API_KEY: your_api_key_here
```

If a referenced variable is not set, Killarr logs an error and exits:

```
Configuration error in <path>: Environment variable 'RADARR_API_KEY' referenced in config is not set.
```

### Global Settings

Settings under the `killarr:` top-level key. All settings have defaults and the entire `killarr:` section is optional — omitting it uses all defaults.

#### `interval`

**Type:** Integer | **Default:** `3600` | **Minimum:** `1`

Seconds to wait between removal cycles.

```yaml
killarr:
  interval: 1800  # Run every 30 minutes
```

#### `dry_run`

**Type:** Boolean | **Default:** `false`

When `true`, stalled items are identified and logged but not removed. No DELETE or POST requests are made. Use this to verify your configuration before enabling real removals.

```yaml
killarr:
  dry_run: true  # Test mode — no removals triggered
```

#### `batch_size`

**Type:** Integer | **Default:** `10`

Maximum number of stalled items to remove per cycle per instance.

- Set to `0` to disable removal entirely (Killarr will still log found items at DEBUG level)
- Set to `-1` for unlimited (remove all stalled items found each cycle)
- Set to a positive integer to limit removals per cycle

```yaml
killarr:
  batch_size: 5    # Remove up to 5 stalled items per cycle
  # batch_size: -1  # Remove all stalled items
  # batch_size: 0   # Disabled — no removals
```

#### `remove_from_client`

**Type:** Boolean | **Default:** `true`

When `true`, passes `removeFromClient=true` to the \*arr DELETE queue API. This tells the \*arr app to also delete the file from the download client (e.g., remove the torrent from qBittorrent or SABnzbd). When `false`, the item is removed from the \*arr queue but the download client entry is left in place.

```yaml
killarr:
  remove_from_client: true
```

#### `blocklist`

**Type:** Boolean | **Default:** `true`

When `true`, passes `blocklist=true` to the \*arr DELETE queue API. This adds the removed release to the \*arr blocklist, preventing it from being grabbed again by automatic searches.

```yaml
killarr:
  blocklist: true
```

#### `search_again`

**Type:** Boolean | **Default:** `true`

When `true`, Killarr triggers a fresh search for the media item after removing the stalled download. This sends a `MoviesSearch` (Radarr), `EpisodeSearch` (Sonarr), or `AlbumSearch` (Lidarr) command to the \*arr instance — the same as clicking "Search" manually. Set to `false` if you prefer to let \*arr's own monitored search handle re-acquisition.

```yaml
killarr:
  search_again: true
```

#### `stagger_interval_seconds`

**Type:** Integer | **Default:** `5` | **Minimum:** `0`

Seconds to wait between individual removal operations within a single cycle. Set to `0` to remove all stalled items in rapid succession. Stagger applies between items, not after the last item.

```yaml
killarr:
  stagger_interval_seconds: 10  # Wait 10s between removals
```

#### `include_tags`

**Type:** List of strings | **Default:** `[]`

When non-empty, only remove stalled items where the media has **any** of the listed tags. Tags are resolved from each \*arr instance at startup and matched case-insensitively. Leave empty (or omit) to process all stalled items regardless of tags.

For Radarr, tags are checked on the queue record directly. For Sonarr, tags are checked on the series. For Lidarr, tags are checked on the artist.

```yaml
killarr:
  include_tags: ["managed"]  # Only remove stalled items tagged "managed"
```

#### `exclude_tags`

**Type:** List of strings | **Default:** `[]`

Skip stalled items where the media has **any** of the listed tags. Tags are matched case-insensitively. When both `include_tags` and `exclude_tags` are configured, exclude takes precedence — an item with an excluded tag is always skipped even if it also has an included tag.

```yaml
killarr:
  exclude_tags: ["protected"]  # Never remove stalled items tagged "protected"
```

### Instance Settings

Settings for individual \*arr instances under the `instances:` key.

#### `type` (required)

**Options:** `radarr`, `sonarr`, `lidarr`

```yaml
instances:
  Movies:
    type: radarr
```

#### `host` (required)

Base URL of the \*arr instance.

**Docker deployments:** Use `http://` with the container hostname (e.g., `http://radarr:7878`). Traffic stays on the internal Docker network.

**HTTPS:** Only works when routing through a reverse proxy with a publicly trusted certificate. Self-signed certificates are not supported.

```yaml
instances:
  Movies:
    host: "http://radarr:7878"  # Docker: container hostname
    # host: "http://localhost:7878"  # Non-Docker: localhost
```

#### `api_key` (required)

API key for authentication. Found in \*arr Settings → General → Security. Never commit `config.yaml` to version control — it is gitignored by default.

#### `enabled`

**Type:** Boolean | **Default:** `false`

Instances are disabled by default as a safety measure. You must explicitly set this to `true` to activate an instance.

#### `weight`

**Type:** Number | **Default:** `1`

Relative priority used only when `batch_size` is a positive integer and multiple instances of the same type are configured. Higher weight = more removals allocated from the batch.

### Per-Instance Killarr Overrides

Any global `killarr:` setting can be overridden for a specific instance by adding a `killarr:` subsection under that instance. This is useful when different instances need different behaviour — for example, a more aggressive batch size for one Radarr instance.

```yaml
killarr:
  batch_size: 10
  blocklist: true

instances:
  Radarr-Main:
    type: radarr
    host: "http://radarr:7878"
    api_key: "key1"
    enabled: true
    # Uses global defaults: batch_size=10, blocklist=true

  Radarr-4K:
    type: radarr
    host: "http://radarr-4k:7879"
    api_key: "key2"
    enabled: true
    killarr:
      batch_size: 3      # Override: only remove 3 per cycle for 4K
      blocklist: false   # Override: don't blocklist 4K releases
```

Instance-level overrides take precedence over global settings. Any setting not specified in the instance override inherits the global value.

### Environment Variable-Only Configuration

Set `KILLARR_CONFIG_SOURCE=env` to have Killarr ignore `config.yaml` entirely and read all configuration from environment variables.

#### Global Settings

Prefix global settings with `KILLARR_GLOBAL_`. All values are type-coerced automatically — `"true"`/`"false"` become booleans, numeric strings become integers.

| Variable | Default | Description |
|---|---|---|
| `KILLARR_GLOBAL_INTERVAL` | `3600` | Run interval in seconds. |
| `KILLARR_GLOBAL_DRY_RUN` | `false` | Log removals without executing them. |
| `KILLARR_GLOBAL_BATCH_SIZE` | `10` | Items to remove per cycle. `0` disables, `-1` is unlimited. |
| `KILLARR_GLOBAL_REMOVE_FROM_CLIENT` | `true` | Delete file from download client on removal. |
| `KILLARR_GLOBAL_BLOCKLIST` | `true` | Add removed release to the blocklist. |
| `KILLARR_GLOBAL_SEARCH_AGAIN` | `true` | Trigger fresh search after removal. |
| `KILLARR_GLOBAL_STAGGER_INTERVAL_SECONDS` | `5` | Delay in seconds between individual removals. |
| `KILLARR_GLOBAL_INCLUDE_TAGS` | `(none)` | Comma-separated tag names. Only remove items with any of these tags. |
| `KILLARR_GLOBAL_EXCLUDE_TAGS` | `(none)` | Comma-separated tag names. Skip items with any of these tags. |

#### Instance Settings

Each instance is identified by a numeric index. Prefix instance fields with `KILLARR_INSTANCE_<INDEX>_`.

| Variable | Required | Description |
|---|---|---|
| `KILLARR_INSTANCE_<n>_NAME` | Yes | Unique name for this instance. |
| `KILLARR_INSTANCE_<n>_TYPE` | Yes | `radarr`, `sonarr`, or `lidarr` (case-insensitive). |
| `KILLARR_INSTANCE_<n>_URL` | Yes | Base URL of the instance (e.g. `http://radarr:7878`). |
| `KILLARR_INSTANCE_<n>_API_KEY` | Yes | API key from the instance's settings page. |
| `KILLARR_INSTANCE_<n>_ENABLED` | No | Defaults to `true`. |
| `KILLARR_INSTANCE_<n>_WEIGHT` | No | Relative removal weight. Defaults to `1`. |

#### Shared Instances with Rangarr

If you already have Rangarr configured via `RANGARR_INSTANCE_*` environment variables, you can tell Killarr to read those instead of defining a separate `KILLARR_INSTANCE_*` set:

```bash
KILLARR_INSTANCE_SOURCE=shared
```

When set, Killarr reads `RANGARR_INSTANCE_<n>_*` for all instance definitions. `KILLARR_GLOBAL_*` settings still apply as normal. This is the env-var equivalent of pointing both tools at the same `config.yaml`.

#### Example

```bash
KILLARR_CONFIG_SOURCE=env
KILLARR_GLOBAL_INTERVAL=3600
KILLARR_GLOBAL_DRY_RUN=false

KILLARR_INSTANCE_0_NAME=Movies
KILLARR_INSTANCE_0_TYPE=radarr
KILLARR_INSTANCE_0_URL=http://radarr:7878
KILLARR_INSTANCE_0_API_KEY=your-api-key

KILLARR_INSTANCE_1_NAME=TV
KILLARR_INSTANCE_1_TYPE=sonarr
KILLARR_INSTANCE_1_URL=http://sonarr:8989
KILLARR_INSTANCE_1_API_KEY=your-api-key
```

Or, if Rangarr is already configured:

```bash
# Killarr-specific settings
KILLARR_CONFIG_SOURCE=env
KILLARR_GLOBAL_DRY_RUN=false
KILLARR_INSTANCE_SOURCE=shared  # Read instances from RANGARR_INSTANCE_* vars

# Shared instance definitions (read by both Rangarr and Killarr)
RANGARR_INSTANCE_0_NAME=Movies
RANGARR_INSTANCE_0_TYPE=radarr
RANGARR_INSTANCE_0_URL=http://radarr:7878
RANGARR_INSTANCE_0_API_KEY=your-api-key
```

---

## Shared Config with Rangarr

Killarr and [Rangarr](https://github.com/JudoChinX/rangarr) can share a single `config.yaml`. Each tool reads its own top-level section and ignores the other's:

- **Rangarr** reads `global:` for its settings
- **Killarr** reads `killarr:` for its settings
- **Both** read `instances:` for connection details

This means you can run both tools against the same config file with no duplication:

```yaml
# Shared config.yaml — works with both Rangarr and Killarr

# Rangarr settings — ignored by Killarr
global:
  interval: 3600
  missing_batch_size: 20
  upgrade_batch_size: 10
  stagger_interval_seconds: 30

# Killarr settings — ignored by Rangarr
killarr:
  interval: 3600
  batch_size: 5
  remove_from_client: true
  blocklist: true
  search_again: true
  stagger_interval_seconds: 10
  dry_run: false

# Shared by both tools
instances:
  Radarr:
    type: radarr
    host: "http://radarr:7878"
    api_key: "YOUR_RADARR_API_KEY"
    enabled: true

  Sonarr:
    type: sonarr
    host: "http://sonarr:8989"
    api_key: "YOUR_SONARR_API_KEY"
    enabled: true
```

**Rangarr co-deployment is not required.** If you are only running Killarr, your config only needs `killarr:` + `instances:`:

```yaml
killarr:
  interval: 3600
  dry_run: false

instances:
  Radarr:
    type: radarr
    host: "http://radarr:7878"
    api_key: "YOUR_API_KEY"
    enabled: true
```

---

## Docker

### Docker Compose

A minimal `compose.yaml`:

```yaml
services:
  killarr:
    image: judochinx/killarr:latest
    container_name: killarr
    hostname: killarr
    restart: unless-stopped
    environment:
      TZ: UTC          # Set your timezone for log timestamps (e.g. America/New_York)
      LOG_LEVEL: INFO  # Use DEBUG for verbose logging
    volumes:
      - ./config.yaml:/app/config/config.yaml:ro
    networks:
      - arr

networks:
  arr:
    external: true
```

**View logs:**
```bash
docker compose logs -f
```

**Update to a new release:**
```bash
docker compose pull
docker compose up -d
```

### Docker Run

```bash
curl -O https://raw.githubusercontent.com/JudoChinX/killarr/main/config.example.yaml
mv config.example.yaml config.yaml
chmod 644 config.yaml  # Required: container runs as UID 65532 (nonroot)
# Edit config.yaml with your *arr API keys and hostnames

docker run -d \
  --name killarr \
  --hostname killarr \
  --restart unless-stopped \
  --network arr \
  -e TZ=UTC \
  -e LOG_LEVEL=INFO \
  -v ./config.yaml:/app/config/config.yaml:ro \
  judochinx/killarr:latest
```

**View logs:**
```bash
docker logs -f killarr
```

**Update to a new release:**
```bash
docker pull judochinx/killarr:latest
docker stop killarr && docker rm killarr
# Re-run the docker run command above
```

### Docker Networking

Killarr and all \*arr containers should share a single, dedicated Docker network. This keeps traffic between containers internal and off the host network stack.

Create the network once:
```bash
docker network create arr
```

In `config.yaml`, use container hostnames instead of `localhost`:
```yaml
instances:
  Radarr:
    type: radarr
    host: "http://radarr:7878"  # Container hostname, not localhost
    api_key: "your_api_key"
    enabled: true
```

If Killarr and your \*arr containers are already on a shared network (e.g., one created for Rangarr), you can reuse the same network — Killarr does not need its own.

---

## Operational Best Practices

### Always Start with Dry Run

Before enabling Killarr on a live system, set `dry_run: true` and run for at least one full cycle. Review the logs to confirm it identifies the right items and would take the right actions. Only set `dry_run: false` once you are satisfied.

```yaml
killarr:
  dry_run: true
  interval: 60  # Short interval for testing
```

```bash
docker compose up -d && docker compose logs -f
```

### Use Tag Filtering for Fine Control

If you have media that should never be auto-removed (e.g., seeding torrents, manually managed items), add a tag in your \*arr app and configure `exclude_tags`:

```yaml
killarr:
  exclude_tags: ["protected", "seeding"]
```

Tags are resolved at startup from each \*arr instance. Adding or removing tags in \*arr requires restarting Killarr to take effect.

### Tune Stagger for Your Setup

The default `stagger_interval_seconds: 5` is conservative. If your \*arr instances are local and responsive, you can reduce this. If you have many stalled items and want to pace removals, increase it.

---

## Troubleshooting

### Connection Errors

#### "Failed to fetch queue" in logs

**Causes:**
1. Wrong URL in `config.yaml` — missing `http://`, wrong port.
2. \*arr instance is unreachable from the Killarr container.
3. Docker networking not configured correctly.

**Solutions:**

1. **Verify URL format:**
   ```yaml
   host: "http://radarr:7878"   # Docker: use container hostname
   host: "http://localhost:7878" # Non-Docker only — won't work inside Docker
   ```

2. **Test connectivity manually:**
   ```bash
   curl http://localhost:7878/api/v3/system/status?apikey=YOUR_API_KEY
   ```

3. **Docker networking:** Killarr and \*arr containers must be on the same Docker network. Use container hostnames in `config.yaml`, not `localhost`.

#### "401 Unauthorized" or "403 Forbidden"

**Cause:** Invalid API key.

**Solution:** Go to Settings → General → Security in the \*arr UI and copy the API key exactly (no extra spaces, case-sensitive).

### No Stalled Items Found

**"No stalled items found this cycle"** is the expected log message when your queues are healthy — this is normal.

If you believe items are stalled but Killarr is not finding them:

1. **Enable debug logging** to see every queue record evaluated:
   ```yaml
   environment:
     LOG_LEVEL: DEBUG
   ```
   Look for `Skipping stalled item (tag filter):` messages — these indicate items are being excluded by tag filtering.

2. **Verify in \*arr UI:** Go to Activity → Queue and check the "Status" column. Killarr detects items with `trackedDownloadStatus = warning` — the \*arr queue should show these as "Warning".

3. **Check tag filtering:** If `include_tags` or `exclude_tags` is configured, verify the tag names match exactly what is set in the \*arr app (case-insensitive, but spelling must match).

### Items Found but Not Removed

**Cause:** `dry_run: true` is set.

**Solution:**
```yaml
killarr:
  dry_run: false
```

### "chmod 644" Reminder

The container runs as UID 65532 (`nonroot`), not your host user. The config file must be readable by this user:

```bash
chmod 644 config.yaml
```

---

## Development Setup

```bash
# Clone the repo
git clone https://github.com/JudoChinX/killarr.git
cd killarr

# Create a virtual environment with Python 3.13+
uv venv --python 3.13 .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dev dependencies
pip install -r requirements-dev.txt

# Run the test suite
pytest

# Run with coverage report
pytest --cov=killarr --cov-report=term-missing

# Linting and formatting
ruff check .
ruff format .

# Type checking
mypy killarr/ tests/

# Security scan
bandit -r killarr/ -lll

# Code quality
pylint killarr/ tests/
```
