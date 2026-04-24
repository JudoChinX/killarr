# Design Spec: Stall Reason Handling

Killarr will be enhanced to differentiate between various stall reasons provided by the *arr instances and apply specific actions based on the reason.

## 1. Overview
Currently, Killarr treats all items with a `trackedDownloadStatus` of `warning` the same way. This design introduces a classification layer that inspects `statusMessages` to group stalls into categories, allowing for granular control over how each type of stall is handled.

## 2. Architecture & Components

### 2.1. Stall Classification (`StallClassifier`)
A new internal utility that parses the `statusMessages` array from *arr queue records. It maps messages to the following categories using keyword matching:

| Category | Typical Messages |
|---|---|
| `no_upgrade` | "Not a Custom Format upgrade...", "do not improve on Existing" |
| `manual_import` | "Manual Import required", "matched to movie by ID" |
| `no_files` | "No files found are eligible for import" |
| `missing_items` | "One or more episodes/tracks expected... were not imported" |
| `tba_title` | "Episode has a TBA title" |
| `stalled` | Fallback for any other `warning` status (e.g., 0 peers, download stalled) |

### 2.2. Named Actions
Actions are simplified into four clear behaviors:

| Action | Behavior |
|---|---|
| `ignore` | **(Default)** Skip the item. No action taken. |
| `remove` | Delete from queue + Delete from download client. |
| `retry` | Delete from queue/client + Trigger new search. |
| `blocklist` | Delete from queue/client + Add to blocklist + Trigger new search. |

## 3. Configuration & Schema

### 3.1. Flattened Structure
Categories are placed directly under the `killarr` key in both global and instance configurations.

```yaml
killarr:
  interval: 3600
  # Global Actions
  stalled: blocklist
  no_upgrade: ignore
  manual_import: ignore
  no_files: remove

instances:
  Radarr:
    killarr:
      no_upgrade: remove  # Instance Override
```

### 3.2. Resolution Logic
For a given stalled item:
1. Classify the item into a category (e.g., `no_upgrade`).
2. Check the instance-level config for that category key.
3. Check the global-level config for that category key.
4. Fallback to the action defined for the `stalled` key.
5. Ultimate fallback: `ignore`.

## 4. Data Flow
1. **Fetch:** `ArrClient` retrieves queue items including `statusMessages`.
2. **Classify:** `StallClassifier` determines the category from the messages.
3. **Resolve:** `ArrClient` looks up the action string (`ignore`, `remove`, etc.) using the resolution hierarchy.
4. **Execute:** `ArrClient` maps the action string to internal API parameters and executes the call.

## 5. Error Handling
- **Unknown Category:** If a message doesn't match any known keywords, it is categorized as `stalled`.
- **Unknown Action:** If a configuration value is not one of the four valid actions, Killarr will log a warning and fallback to `ignore`.
- **API Failure:** If a removal or search call fails, Killarr logs the error and continues to the next item in the cycle.

## 6. Testing Strategy
- **Unit Tests:**
    - `StallClassifier` tests for correct mapping of various *arr message strings.
    - Config resolution tests to verify global vs. instance precedence.
- **Integration Tests:**
    - Mock API responses for each of the four named actions to ensure correct parameter transmission (`removeFromClient`, `blocklist`, etc.).
- **Regression:** Ensure that the existing tag filtering and batch size logic still apply correctly to the categorized items.
