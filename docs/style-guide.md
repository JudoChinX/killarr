# Killarr Style Guide

This guide codifies all code and test conventions for Killarr. Primary audience is AI agents
writing or reviewing code; secondary audience is human contributors.

For contribution workflow (branching, PRs, commit messages), see
[CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Table of Contents

- [General Conventions](#general-conventions)
- [Naming](#naming)
- [Module Structure](#module-structure)
- [Docstrings](#docstrings)
- [Type Hints](#type-hints)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Tooling Reference](#tooling-reference)

---

## General Conventions

### Single Quotes

All strings use single quotes. Ruff enforces this via `quote-style = "single"`.

```python
# Do
message = f'Client {name} registered.'
label = 'Disabled'

# Don't
message = f'Client {name} registered.'
label = 'Disabled'
```

### f-strings

Prefer f-strings over `.format()` or `%`-style interpolation.

```python
# Do
logger.info(f'[{self.name}] Removed (stalled): {title} ({index}/{total})')

# Don't
logger.info('[{}] Removed (stalled): {} ({}/{})'.format(self.name, title, index, total))
```

### Early Returns

No more than 2 early returns per function.

```python
# Do — two returns maximum (from arr.py)
def _is_stalled(self, record: dict) -> bool:
    """Return True if the record is considered stalled by the arr app."""
    return record.get('trackedDownloadStatus') == 'warning'


# Don't — three or more returns
def _classify(value: str) -> str:
    """Classify a status value."""
    if value == 'warning':
        return 'stalled'
    if value == 'ok':
        return 'healthy'
    if value == 'error':
        return 'failed'
    return 'unknown'
```

### Variable Names

Variable names must be at least 3 characters.

```python
# Do
ids = [item[0] for item in items]
url = f'{self.url}{self.ENDPOINT_QUEUE}/{queue_id}'

# Don't
id = record['id']
fn = self._get_record_title
```

### Comments

Write comments only when the WHY is non-obvious — a hidden constraint, a workaround, a subtle
invariant. Never describe what the code does.

```python
# Do — explains a non-obvious side-effect ordering constraint
killarr_overrides = instance.pop('killarr', {})
if 'host' in instance:
    instance['url'] = instance.pop('host')
# Promote killarr overrides to top-level so main.py can pick them up
instance.update(killarr_overrides)

# Don't — describes what the code does
# Pop the killarr key and check if host is in the instance
killarr_overrides = instance.pop('killarr', {})
```

### Function Ordering

Private functions (`_name`) come before all public functions within a module. Within each
group, functions are sorted alphabetically by name.

```python
# Do (excerpt from main.py — all private functions precede all public ones, each group sorted)
def _calculate_eta(...): ...           # private, 'c'
def _format_cycle_info(...): ...       # private, 'f'
def _get_setting(...): ...             # private, 'g'
def _load_config_from_paths(...): ...  # private, 'l'
def _log_killarr_start(...): ...       # private, 'lo'
def _run_removal_cycle(...): ...       # private, 'r'
def build_arr_clients(...): ...        # public, 'b'
def run(...): ...                      # public, 'r'

# Don't — unsorted or public before private
def run(...): ...
def _get_setting(...): ...
def build_arr_clients(...): ...
```

---

## Naming

| Entity | Convention | Example |
|---|---|---|
| Private function | `_snake_case` | `_get_setting`, `_run_removal_cycle` |
| Public function | `snake_case` | `build_arr_clients`, `get_stalled_items` |
| Public module constant | `UPPER_CASE` | `ENDPOINT_QUEUE`, `SETTINGS_SCHEMA` |
| Private module constant | `_UPPER_CASE` | `_CLIENT_MAP` |
| Class | `PascalCase` | `ArrClient`, `RadarrClient`, `ClientBuilder` |
| Type alias | `type Name = ...` | `type QueueItem = tuple[int, int, str, str]` |
| Test case dict | `_snake_case_cases` | `_parse_config_cases`, `_is_stalled_cases` |
| Builder class | `<Subject>Builder` | `ClientBuilder`, `RadarrQueueBuilder` |

---

## Module Structure

Every file follows this top-to-bottom ordering:

1. Module docstring
2. Standard library imports (one per line, sorted)
3. Third-party imports (one per line, sorted)
4. Local imports (one per line, sorted)
5. Module-level type aliases and constants
6. Private functions (alphabetical)
7. Public functions and classes (interleaved alphabetically by name)
8. `if __name__ == '__main__':` guard (when present)

The isort configuration enforces `force-single-line = true` — each import is on its own line.

```python
# Do — canonical module structure (illustrative excerpt from main.py and arr.py)
"""Killarr entry point.

Orchestrates stalled download removal across multiple *arr instances by
fetching queue items, removing those in warning status, and repeating at
scheduled intervals.
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from killarr.clients.arr import ArrClient
from killarr.clients.arr import RadarrClient
from killarr.config_parser import load_config
from killarr.config_parser import load_config_from_env

_CLIENT_MAP: dict[str, type[ArrClient]] = {
    'lidarr': LidarrClient,
    'radarr': RadarrClient,
    'sonarr': SonarrClient,
}

type QueueItem = tuple[int, int, str, str]


def _get_setting(settings: dict, key: str) -> Any:
    """Return setting value, falling back to its schema default."""
    ...


def build_arr_clients(instances_config: dict, settings: dict) -> list[ArrClient]:
    """Instantiate all *arr clients declared in the config."""
    ...
```

---

## Docstrings

### Module Docstrings

Every module starts with a docstring. A one-sentence summary is sufficient for simple modules;
add a paragraph for complex ones.

```python
# Do — single sentence (from arr.py)
"""*arr API clients: base class and app-specific subclasses for queue management."""

# Do — multi-sentence (from main.py)
"""Killarr entry point.

Orchestrates stalled download removal across multiple *arr instances by
fetching queue items, removing those in warning status, and repeating at
scheduled intervals.
"""
```

### Private Functions

Private functions get a **single-line docstring only**. No `Args:` or `Returns:` block.

```python
# Do (from arr.py)
def _is_tag_filtered_out(self, record: dict) -> bool:
    """Return True if this record should be skipped due to tag filtering rules."""
    ...


# Don't — Args block on a private function
def _is_tag_filtered_out(self, record: dict) -> bool:
    """Check tag filtering.

    Args:
        record: The queue record dict.

    Returns:
        True if filtered out.
    """
    ...
```

### Public Functions and Methods

Public functions use Google style: a summary line, then `Args:`, `Returns:`, and `Raises:` as
applicable. Omit sections that don't apply.

```python
# Do (from main.py)
def build_arr_clients(
    instances_config: dict,
    settings: dict,
    client_registry: dict[str, type[ArrClient]] | None = None,
) -> list[ArrClient]:
    """Instantiate all *arr clients declared in the config.

    Args:
        instances_config: The ``instances`` section of the config dict.
        settings: The ``global_settings`` section of the config dict.
        client_registry: Optional client type registry (defaults to _CLIENT_MAP).

    Returns:
        Flat list of instantiated *arr client objects.
    """
    ...
```

### @override Methods

`@override` methods get **no docstring**. The base class docstring is sufficient.

```python
# Do (from arr.py subclasses)
@override
def _get_record_title(self, record: dict) -> str:
    return record.get('title', f'Queue item {record.get("id", "Unknown")}')


# Don't — docstring duplicates the base
@override
def _get_record_title(self, record: dict) -> str:
    """Get the record title."""
    return record.get('title', f'Queue item {record.get("id", "Unknown")}')
```

### Docstring Rules

- All docstrings end with punctuation.
- Never restate the function name (don't write `"Returns the title."` for `get_record_title`).
- Use double-backtick quoting for inline code references in docstrings: `` ``instances`` ``.

---

## Type Hints

### All Signatures Must Be Typed

Mypy enforces `disallow_untyped_defs`. Every parameter and return type must be annotated.

```python
# Do
def _get_setting(settings: dict, key: str) -> Any:
    """Return setting value, falling back to its schema default."""
    ...


# Don't
def _get_setting(settings, key): ...
```

### Type Aliases

Use the `type` keyword (Python 3.12+ PEP 695 syntax) for module-level type aliases.

```python
# Do (from arr.py)
type QueueItem = tuple[int, int, str, str]

# Don't
QueueItem = tuple[int, int, str, str]
```

### Self for Fluent Builders

Use `Self` from `typing` for builder return types in class hierarchies — where subclasses need
to preserve the concrete type through the chain. For non-subclassed concrete builders, a forward
string reference annotation (`-> 'ClassName'`) is also acceptable.

```python
# Do (from builders.py) — Self preserves the subclass type through the chain
from typing import Self


def with_id(self, queue_id: int) -> Self:
    """Set the queue record ID."""
    self._data['id'] = queue_id
    return self


# Don't — string annotation on a base class loses the concrete subclass type
def with_id(
    self, queue_id: int
) -> '_QueueRecordBuilder':  # RadarrQueueBuilder.with_id() would return _QueueRecordBuilder
    ...
```

### @override

The `@override` decorator from `typing` is required when overriding a base class method.

```python
# Do (from arr.py)
from typing import override


@property
@override
def _command_name(self) -> str:
    return 'MoviesSearch'


# Don't — missing decorator
@property
def _command_name(self) -> str:
    return 'MoviesSearch'
```

### Any

Use `Any` only at true system boundaries: test helpers and external API response shapes where
the type genuinely cannot be known.

```python
# Do — external API response shape (from helpers.py)
def mock_http_response(data: Any) -> Any:
    """Create a mock HTTP response object."""
    ...


# Don't — internal code with known types
def _remove_single(queue_id: Any, media_id: Any, title: Any) -> Any: ...
```

---

## Error Handling

### Validate at Boundaries Only

Validate user input and external data at entry points (config loading, API responses). Trust
internal code — do not add defensive guards for states that cannot occur.

```python
# Do — validate at the config loading boundary (from main.py)
try:
    config = load_config(config_path)
except ValueError as error:
    error_message = f'Configuration error in {config_path}: {error}'


# Don't — defensive guard inside pure internal logic
def _get_setting(settings: dict, key: str) -> Any:
    """Return setting value, falling back to its schema default."""
    if not isinstance(settings, dict):  # impossible in internal use
        raise TypeError('settings must be a dict')
    ...
```

### Catch Specific Exceptions

Never use bare `except:`. Catch the specific exception type you expect.

```python
# Do (from arr.py)
try:
    response = self.session.delete(url, params=params, timeout=15)
    response.raise_for_status()
except requests.RequestException as error:
    logger.error(f'[{self.name}] Failed to remove {title} (ID: {queue_id}): {error}')
    return

# Don't
try:
    response = self.session.delete(url, params=params, timeout=15)
except:
    pass
```

### Logging

Log errors and warnings with f-string context. Never log API keys, tokens, or other secrets.

```python
# Do
logger.error(f'[{self.name}] Failed to fetch queue: {error}')
logger.warning(f"Client '{name}' is using a non-HTTPS URL ({self.url}). API keys will be transmitted in plaintext.")
```

Double quotes are used in the second example because the string contains embedded single quotes;
Ruff permits this to avoid escaping.

```python
# Don't — leaks authentication headers
logger.debug(f'Request headers: {self.session.headers}')
```

### Startup Failures

Use `sys.exit(1)` for unrecoverable startup failures — not exceptions.

```python
# Do (from main.py)
if not config:
    sys.exit(1)

if not active_clients:
    logger.warning("No *arr instances are configured. Add at least one entry under 'instances' to begin.")
    sys.exit(1)
```

---

## Testing

### Case Dict + Parametrize Pattern

Test data lives in a module-level dict named `_<function>_cases`. Dict keys become the
parametrize `ids`. Test functions receive unpacked values, not the dict itself.

```python
# Do (from test_config_parser.py)
_parse_config_cases = {
    'no_killarr_section_uses_defaults': {
        'config_data': make_config(),
        'expected_result': {
            'global_settings': {'interval': 3600, 'batch_size': 10, 'stagger_interval_seconds': 5},
        },
    },
    'missing_instances_raises': {
        'config_data': {'killarr': {}},
        'expected_error': "Missing required top-level key: 'instances'",
    },
    # ... additional cases follow the same pattern
}


@pytest.mark.parametrize(
    'config_data, expected_error, expected_result',
    [
        (case['config_data'], case.get('expected_error'), case.get('expected_result'))
        for case in _parse_config_cases.values()
    ],
    ids=list(_parse_config_cases.keys()),
)
def test_parse_config(config_data: Any, expected_error: Any, expected_result: Any) -> None:
    """Test parse_config validates configuration structure and values."""
    if expected_error:
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            parse_config(config_data)
    else:
        assert_config_result(parse_config(config_data), expected_result)


# Don't — data inlined in parametrize, no ids
@pytest.mark.parametrize(
    'config_data, expected_error',
    [
        ({'killarr': {}}, "Missing required top-level key: 'instances'"),
    ],
)
def test_parse_config(config_data, expected_error):
    with pytest.raises(ValueError, match=expected_error):
        parse_config(config_data)
```

### Builder Pattern

Use builders from `tests/builders.py` to construct test objects. Extend `tests/builders.py`
when you need a new builder — do not inline raw dicts in tests.

```python
# Do (from test_arr_client.py)
from tests.builders import ClientBuilder
from tests.builders import RadarrQueueBuilder

client = ClientBuilder().radarr().with_settings(batch_size=5, dry_run=True).build()
record = RadarrQueueBuilder().warning().with_id(99).with_movie_id(42).build()

# Don't — inline construction
client = RadarrClient(name='test', url='http://test', api_key='key', settings={})
record = {'id': 99, 'movieId': 42, 'trackedDownloadStatus': 'warning', 'tags': [], 'action': 'remove'}
```

### Error String Matching

Always wrap error strings in `re.escape()` when using `pytest.raises(match=...)`. This prevents
special characters in error messages from being interpreted as regex.

```python
# Do
with pytest.raises(ValueError, match=re.escape("Missing or empty 'api_key' for instance 'r'.")):
    parse_config(config)

# Don't — parentheses and quotes are regex metacharacters
with pytest.raises(ValueError, match="Missing or empty 'api_key' for instance 'r'."):
    parse_config(config)
```

### Test Function Naming

- Standalone test: `test_<function>_<scenario>`
- Parametrized test: `test_<function>` (the case dict key serves as the scenario id)

```python
# Do
def test_parse_config_host_not_in_result(...): ...  # standalone
def test_parse_config(...): ...                     # parametrized — scenario from case key

# Don't
def test_1(...): ...
def test_parse_config_missing_instances_raises_case(...): ...  # scenario already in the id
```

### Fixtures

Declare fixtures with `@pytest.fixture` at the top of the test file, before the first test.
For fixtures shared across files, use `tests/conftest.py`.

Use `monkeypatch` for simple attribute replacement. Annotate `yield`-based fixtures with
`Generator[None, None, None]`; fixtures that only call `monkeypatch.setattr` return `None`.

```python
# Do (from conftest.py) — monkeypatch-based, no yield needed
@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block all unmocked HTTP requests to prevent accidental network calls."""

    def mocked_request(*args: object, **kwargs: object) -> None:
        raise UnmockedNetworkError(f'Unmocked network call attempted: {args} {kwargs}')

    monkeypatch.setattr(requests.Session, 'request', mocked_request)


# Don't — missing return type annotation (mypy will flag this)
@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    monkeypatch.setattr(requests.Session, 'request', ...)
```

`tests/conftest.py` provides two `autouse` fixtures active for every test:

- `block_network` — monkeypatches `requests.Session.request` to raise `UnmockedNetworkError` on
  any unmocked HTTP call. This is the enforcement layer; if a test hits the network it fails loudly.
- `pin_time` — pins `datetime.datetime.now()` to a fixed timestamp (`FIXED_NOW`) and suppresses
  real sleeping via `time.sleep`. Keeps all time-dependent tests deterministic.

### Deterministic Time

Use the `pin_time` autouse fixture (from `conftest.py`) to freeze time in any test that depends
on `datetime.datetime.now()`. The fixed timestamp is `FIXED_NOW = datetime.datetime(2026, 4, 23, 12, 0, 0, tzinfo=datetime.UTC)`.

If a test needs to assert on a specific timestamp, reference `FIXED_NOW` directly rather than
calling `datetime.datetime.now()` at runtime.

```python
# Do — reference the constant; pin_time guarantees they match
from tests.conftest import FIXED_NOW

assert event.timestamp == FIXED_NOW

# Don't — calling now() at runtime may drift from the pinned value
assert event.timestamp == datetime.datetime.now(tz=datetime.UTC)
```

### Nested Test Structure

Tests are organized into three directories that mirror the testing pyramid:

| Directory | Contains | Example |
|---|---|---|
| `tests/unit/` | Pure logic with no I/O or external state | `test_classifier.py`, `test_config_parser.py` |
| `tests/integration/` | Components wired together, HTTP mocked | `test_arr_client.py` |
| `tests/system/` | Full `run()` loop, fixtures loaded from JSON | `test_main.py` |

JSON fixtures live in `tests/fixtures/<arr_type>/`. System tests load fixtures from disk using
`_load_fixture(arr_type, filename)` so that realistic API shapes are version-controlled and
reviewable separately from test logic.

```python
# Do (from tests/system/test_main.py)
_FIXTURES_DIR = Path(__file__).parent.parent / 'fixtures'


def _load_fixture(arr_type: str, filename: str) -> dict:
    """Load a JSON fixture file from the fixtures directory."""
    return json.loads((_FIXTURES_DIR / arr_type / filename).read_text())


# In the test:
queue_data = _load_fixture('radarr', 'queue.json')
with patch('requests.Session.get', return_value=mock_http_response(queue_data)):
    run()

# Don't — inline construction duplicates API shape knowledge across tests
with patch('requests.Session.get', return_value=mock_queue_response([])):
    run()
```

### Mocking HTTP Sessions

Use instance-level assignment when the client object is available in the test:

```python
# Do — instance-level (test_arr_client.py)
client = ClientBuilder().radarr().build()
client.session.get = MagicMock(return_value=mock_queue_response(records))
```

Use class-level `patch` when the client is constructed internally (e.g., system tests that call
`run()` directly and don't have access to the client instance). Load response data from a JSON
fixture rather than constructing it inline:

```python
# Do — class-level (system tests in test_main.py)
queue_data = _load_fixture('radarr', 'queue.json')
with patch('requests.Session.get', return_value=mock_http_response(queue_data)):
    run()
```

Both approaches bypass the `block_network` fixture safely: replacing `get` at either level
prevents the call from reaching `request`, so the fixture's `UnmockedNetworkError` is never raised.

### Log Assertions

Assert log output via `caplog` with an explicit log level.

```python
# Do (from test_arr_client.py)
def test_fetch_all_queue_handles_network_error(caplog: Any) -> None:
    """Test that a network error during queue fetch logs an error and returns an empty list."""
    client = ClientBuilder().radarr().build()
    client.session.get = MagicMock(side_effect=requests.exceptions.ConnectionError('down'))
    with caplog.at_level(logging.ERROR):
        result = client._fetch_all_queue()
    assert 'Failed to fetch queue' in caplog.text


# Don't — no level specified
def test_logs_error(caplog):
    run_thing()
    assert 'something' in caplog.text
```

### Test Data

No identifying information in test data. Use generic placeholders.

```python
# Do
name = 'test'
url = 'http://test'
api_key = 'testkey'

# Don't
name = 'My Radarr'
url = 'http://192.168.1.50:7878'
api_key = 'abc123realkey'
```

### Coverage

The 95% coverage floor is enforced by Pytest (`--cov-fail-under=95`). Every new function or
branch requires a corresponding test.

---

## Tooling Reference

| Tool | Purpose | Command |
|---|---|---|
| Ruff | Lint + format | `ruff check . && ruff format .` |
| Pylint | Code quality | `pylint killarr/ tests/` |
| Mypy | Type checking | `mypy killarr/ tests/` |
| Bandit | Security (high severity only) | `bandit -r killarr/ -lll` |
| Pytest | Tests + 95% coverage | `pytest` |

To auto-fix linting issues:

```bash
ruff check --fix .
```
