# User Guide

Complete guide to installing, configuring, and operating Killarr.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (Docker)](#quick-start-docker)
- [Configuration Sources](#configuration-sources)
- [Configuration Reference](#configuration-reference)
  - [Global Settings](#global-settings)
  - [Stall Actions](#stall-actions)
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

Maximum number of stalled items to remove per cycle across all instances combined.

- Set to `0` to disable removal entirely (Killarr will still log found items at DEBUG level)
- Set to `-1` for unlimited (remove all stalled items found each cycle)
- Set to a positive integer to limit removals per cycle

```yaml
killarr:
  batch_size: 5    # Remove up to 5 stalled items per cycle
  # batch_size: -1  # Remove all stalled items
  # batch_size: 0   # Disabled — no removals
```

#### `interleave_instances`

**Type:** Boolean | **Default:** `false`

When `false` (default), all stalled items from the first instance are removed before moving to the next. When `true`, items from different instances alternate in the removal queue — Killarr removes one item from instance A, then one from instance B, and so on.

```yaml
killarr:
  interleave_instances: true  # Alternate between instances during removal
```

#### `stagger_interval_seconds`

**Type:** Integer | **Default:** `5` | **Minimum:** `0`

Seconds to wait between individual removal operations within a single cycle. Set to `0` to remove all stalled items in rapid succession. Stagger applies between items, not after the last item.

```yaml
killarr:
  stagger_interval_seconds: 10  # Wait 10s between removals
```

#### `active_hours`

**Type:** String | **Default:** `""` (all hours)

Restricts removal cycles to a configured time window. Outside this window, Killarr skips the cycle and sleeps until the window opens. Format is `HH:MM-HH:MM` in 24-hour time. Overnight windows that cross midnight are supported.

Leave empty (or omit) to run at all hours.

```yaml
killarr:
  active_hours: "06:00-23:00"   # Only remove between 6am and 11pm
  # active_hours: "22:00-06:00" # Overnight window (crosses midnight)
```

#### `removal_order`

**Type:** String | **Default:** `api_order` | **Options:** `api_order`, `age_ascending`, `age_descending`

Controls the order in which stalled items are processed within a cycle.

- `api_order` — process items in the order returned by the \*arr API (default)
- `age_ascending` — process oldest stalled items first (lowest `added` timestamp first)
- `age_descending` — process newest stalled items first (highest `added` timestamp first)

Items with no `added` timestamp sort last in `age_ascending` order and first in `age_descending` order.

```yaml
killarr:
  removal_order: age_ascending  # Process oldest stalled items first
```

#### `retry_interval_minutes`

**Type:** Integer | **Default:** `0` (disabled)

Per-media cooldown period in minutes. When a stalled item is actioned, its media ID is recorded with a timestamp. If the same media ID appears stalled again within the cooldown window, it is skipped until the interval expires.

This prevents repeatedly actioning the same media in back-to-back cycles — useful when a replacement download stalls immediately after the original was removed.

```yaml
killarr:
  retry_interval_minutes: 30  # Skip re-actioning the same media for 30 minutes
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

### Stall Actions

Killarr classifies each stalled item into a category based on its `statusMessages` and performs a named action. Actions can be configured globally under `killarr:` or per instance.

#### Valid Actions

| Action | Description |
|---|---|
| `ignore` | Skip the item. No action taken. (Default for all categories) |
| `remove` | Delete from queue and download client. No new search. |
| `retry` | Delete from queue and download client, then trigger a fresh search. |
| `blocklist` | Delete from queue/client, add release to blocklist, and trigger fresh search. |

#### Stall Categories

| Category | Description |
|---|---|
| `stalled` | Generic fallback for reasons not matching other categories (e.g., 0 peers). |
| `no_upgrade` | "Not a Custom Format upgrade for existing [media]". |
| `manual_import` | "Manual import required" or matched to media by ID. |
| `no_files` | "No files found are eligible for import". |
| `missing_items` | "Episodes/tracks missing from the release". |
| `tba_title` | "TBA title" (common in Sonarr for unannounced episodes). |
| `dangerous_file` | "Potentially dangerous file extension" (e.g., `.exe`, `.iso`). |
| `no_messages` | Stall detected but no status messages were provided by the \*arr app. |
| `unknown` | Status messages are present but did not match any known patterns. |

#### Configuration Example

```yaml
killarr:
  stalled: blocklist     # Most stalled items should be blocklisted and retried
  no_upgrade: remove     # Just remove items that don't improve on existing
  manual_import: ignore  # Leave items requiring manual intervention alone
  no_messages: retry     # Retry if no specific reason is given
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

Relative priority for slot allocation when `batch_size` limits total removals per cycle. Higher weight = proportionally more removal slots from the global batch allocated to this instance.

### Per-Instance Killarr Overrides

Any global `killarr:` setting (including actions) can be overridden for a specific instance by adding a `killarr:` subsection under that instance.

```yaml
killarr:
  batch_size: 10
  stalled: blocklist

instances:
  Radarr-Main:
    type: radarr
    host: "http://radarr:7878"
    api_key: "key1"
    enabled: true
    # Uses global defaults: batch_size=10, stalled=blocklist

  Radarr-4K:
    type: radarr
    host: "http://radarr-4k:7879"
    api_key: "key2"
    enabled: true
    killarr:
      batch_size: 3       # Override: only remove 3 per cycle for 4K
      stalled: remove     # Override: don't blocklist 4K releases, just remove
```

### Environment Variable-Only Configuration

Set `KILLARR_CONFIG_SOURCE=env` to have Killarr ignore `config.yaml` entirely and read all configuration from environment variables.

#### Global Settings

Prefix global settings with `KILLARR_GLOBAL_`.

| Variable | Default | Description |
|---|---|---|
| `KILLARR_GLOBAL_INTERVAL` | `3600` | Run interval in seconds. |
| `KILLARR_GLOBAL_DRY_RUN` | `false` | Log removals without executing them. |
| `KILLARR_GLOBAL_BATCH_SIZE` | `10` | Items to remove per cycle. `0` disables, `-1` is unlimited. |
| `KILLARR_GLOBAL_INTERLEAVE_INSTANCES` | `false` | Alternate items between instances during removal. |
| `KILLARR_GLOBAL_STAGGER_INTERVAL_SECONDS` | `5` | Delay in seconds between individual removals. |
| `KILLARR_GLOBAL_ACTIVE_HOURS` | `(none)` | Time window for removals in `HH:MM-HH:MM` format (e.g. `06:00-23:00`). |
| `KILLARR_GLOBAL_REMOVAL_ORDER` | `api_order` | Item processing order: `api_order`, `age_ascending`, or `age_descending`. |
| `KILLARR_GLOBAL_RETRY_INTERVAL_MINUTES` | `0` | Per-media cooldown in minutes. `0` disables. |
| `KILLARR_GLOBAL_INCLUDE_TAGS` | `(none)` | Comma-separated tag names. |
| `KILLARR_GLOBAL_EXCLUDE_TAGS` | `(none)` | Comma-separated tag names. |
| `KILLARR_GLOBAL_STALLED` | `ignore` | Action for `stalled` category. |
| `KILLARR_GLOBAL_NO_UPGRADE` | `ignore` | Action for `no_upgrade` category. |
| `KILLARR_GLOBAL_MANUAL_IMPORT` | `ignore` | Action for `manual_import` category. |
| `KILLARR_GLOBAL_NO_FILES` | `ignore` | Action for `no_files` category. |
| `KILLARR_GLOBAL_MISSING_ITEMS` | `ignore` | Action for `missing_items` category. |
| `KILLARR_GLOBAL_TBA_TITLE` | `ignore` | Action for `tba_title` category. |
| `KILLARR_GLOBAL_DANGEROUS_FILE` | `ignore` | Action for `dangerous_file` category. |
| `KILLARR_GLOBAL_NO_MESSAGES` | `ignore` | Action for `no_messages` category. |
| `KILLARR_GLOBAL_UNKNOWN` | `ignore` | Action for `unknown` category. |

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

When set, Killarr reads `RANGARR_INSTANCE_<n>_*` for all instance definitions. `KILLARR_GLOBAL_*` settings still apply as normal.

---

## Shared Config with Rangarr

Killarr and [Rangarr](https://github.com/JudoChinX/rangarr) can share a single `config.yaml`. Each tool reads its own top-level section and ignores the other's:

- **Rangarr** reads `global:` for its settings
- **Killarr** reads `killarr:` for its settings
- **Both** read `instances:` for connection details

This means you can run both tools against the same config file with no duplication.

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
      TZ: UTC          # Set your timezone for log timestamps
      LOG_LEVEL: INFO  # Use DEBUG for verbose logging
    volumes:
      - ./config.yaml:/app/config/config.yaml:ro
    networks:
      - arr

networks:
  arr:
    external: true
```

### Docker Run

```bash
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

### Docker Networking

Killarr and all \*arr containers should share a single, dedicated Docker network. This keeps traffic between containers internal and off the host network stack.

---

## Operational Best Practices

### Always Start with Dry Run

Before enabling Killarr on a live system, set `dry_run: true` and run for at least one full cycle. Review the logs to confirm it identifies the right items and would take the right actions. Only set `dry_run: false` once you are satisfied.

### Use Tag Filtering for Fine Control

If you have media that should never be auto-removed (e.g., seeding torrents, manually managed items), add a tag in your \*arr app and configure `exclude_tags`.

---

## Troubleshooting

### Connection Errors

#### "Failed to fetch queue" in logs

**Causes:**
1. Wrong URL in `config.yaml` — missing `http://`, wrong port.
2. \*arr instance is unreachable from the Killarr container.
3. Docker networking not configured correctly.

#### "401 Unauthorized" or "403 Forbidden"

**Cause:** Invalid API key.

### No Stalled Items Found

**"No stalled items found this cycle (Evaluated: X)"** is normal if your queues are healthy. The "Evaluated" count shows the total number of items found in the queue across all pages before filtering for stalls.

If you believe items are stalled but Killarr is not finding them:

1. **Enable debug logging** to see every queue record evaluated (`LOG_LEVEL=DEBUG`). You will now see detailed skip reasons (e.g., `action: ignore`, `tag filter`, or `not_stalled`).
2. **Verify in \*arr UI:** Go to Activity → Queue. Killarr detects items with "Warning" status.


### "chmod 644" Reminder

The container runs as UID 65532 (`nonroot`). The config file must be world-readable:

```bash
chmod 644 config.yaml
```

---

## Development Setup

See the [Style Guide](style-guide.md) for detailed coding conventions.

```bash
# Clone the repo
git clone https://github.com/JudoChinX/killarr.git
cd killarr

# Install all dependencies (including dev)
uv sync

# Run the test suite
uv run pytest
```
