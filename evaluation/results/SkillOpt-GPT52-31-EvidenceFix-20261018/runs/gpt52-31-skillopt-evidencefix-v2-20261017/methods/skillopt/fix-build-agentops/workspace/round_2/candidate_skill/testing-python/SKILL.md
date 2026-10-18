---
name: testing-python
description: Write and evaluate effective Python tests using pytest. Use when writing tests, reviewing test code, debugging test failures, or improving test coverage. Covers test design, fixtures, parameterization, mocking, and async testing.
---

# Writing Effective Python Tests

## Core Principles

Every test should be **atomic**, **self-contained**, and test **single functionality**. A test that tests multiple things is harder to debug and maintain.

## Test Structure

### Atomic unit tests

Each test should verify a single behavior. The test name should tell you what's broken when it fails. Multiple assertions are fine when they all verify the same behavior.

```python
# Good: Name tells you what's broken
def test_user_creation_sets_defaults():
    user = User(name="Alice")
    assert user.role == "member"
    assert user.id is not None
    assert user.created_at is not None

# Bad: If this fails, what behavior is broken?
def test_user():
    user = User(name="Alice")
    assert user.role == "member"
    user.promote()
    assert user.role == "admin"
    assert user.can_delete_others()
```

### Use parameterization for variations of the same concept

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("World", "WORLD"),
    ("", ""),
    ("123", "123"),
])
def test_uppercase_conversion(input, expected):
    assert input.upper() == expected
```

### Use separate tests for different functionality

Don't parameterize unrelated behaviors. If the test logic differs, write separate tests.

## Project-Specific Rules

### No async markers needed



Make async behavior deterministic:
- Avoid `time.sleep()` to “wait for uploads/flushes”. Prefer explicit `await client.flush()` / `await queue.join()` / events or condition-based waits.
- If you must wait, poll with a timeout on an observable condition (queue empty, request count reached) rather than sleeping a fixed duration.
This project uses `asyncio_mode = "auto"` globally. Write async tests without decorators:

```python
# Correct
async def test_async_operation():
    result = await some_async_function()
    assert result == expected

# Wrong - don't add this
@pytest.mark.asyncio
async def test_async_operation():
    ...
```

### Imports at module level

Put ALL imports at the top of the file:

```python
# Correct
import pytest
from fastmcp import FastMCP
from fastmcp.client import Client

async def test_something():
    mcp = FastMCP("test")
    ...

# Wrong - no local imports
async def test_something():
    from fastmcp import FastMCP  # Don't do this
    ...
```

### Use in-memory transport for testing

Pass FastMCP servers directly to clients:

```python
from fastmcp import FastMCP
from fastmcp.client import Client

mcp = FastMCP("TestServer")

@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"

async def test_greet_tool():
    async with Client(mcp) as client:
        result = await client.call_tool("greet", {"name": "World"})
        assert result[0].text == "Hello, World!"
```

Only use HTTP transport when explicitly testing network features.

### Inline snapshots for complex data

Use `inline-snapshot` for testing JSON schemas and complex structures:

```python
from inline_snapshot import snapshot

def test_schema_generation():
    schema = generate_schema(MyModel)
    assert schema == snapshot()  # Will auto-populate on first run
```

Commands:
- `pytest --inline-snapshot=create` - populate empty snapshots
- `pytest --inline-snapshot=fix` - update after intentional changes

## Fixtures


### State isolation (singletons, caches, request history)

Many “passes alone, fails in suite” issues come from shared mutable state: module-level singletons (global `client`/`session`), cached config, background workers, or accumulated request-mock history.

Prefer **function-scoped** fixtures and add an **autouse reset** fixture when the library under test uses globals:

```python
import pytest
import agentops  # or your library

@pytest.fixture(autouse=True)
def _reset_global_state(monkeypatch):
    # Example patterns — adapt to the project’s actual globals.
    # Reset singleton/client/session references
    monkeypatch.setattr(agentops, "_client", None, raising=False)
    monkeypatch.setattr(agentops, "_session", None, raising=False)

    # Clear caches / registries that affect later tests
    monkeypatch.setattr(agentops, "_cache", {}, raising=False)

    yield

    # Ensure background work is fully drained before next test
    c = getattr(agentops, "client", None)
    if c is not None:
        flush = getattr(c, "flush", None)
        shutdown = getattr(c, "shutdown", None)
        if callable(flush):
            flush()
        if callable(shutdown):
            shutdown()
```

When using `requests-mock`, ensure each test gets a fresh mocker fixture (or explicitly clear history) so `len(request_history)` isn’t affected by prior tests.

Red flags indicating leakage:
- logs like “session already started” / “cannot start session”
- request count assertions changing based on order
- tags/config persisting across tests
### Prefer function-scoped fixtures

```python
@pytest.fixture
def client():
    return Client()

async def test_with_client(client):
    result = await client.ping()
    assert result is not None
```

### Use `tmp_path` for file operations

```python
def test_file_writing(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("content")
    assert file.read_text() == "content"
```

## Mocking

### Mock at the boundary

```python
from unittest.mock import patch, AsyncMock

async def test_external_api_call():
    with patch("mymodule.external_client.fetch", new_callable=AsyncMock) as mock:
        mock.return_value = {"data": "test"}
        result = await my_function()
        assert result == {"data": "test"}
```

### Don't mock what you own

Test your code with real implementations when possible. Mock external services, not internal classes.

## Test Naming

Use descriptive names that explain the scenario:

```python
# Good
def test_login_fails_with_invalid_password():
def test_user_can_update_own_profile():
def test_admin_can_delete_any_user():

# Bad
def test_login():
def test_update():
def test_delete():
```

## Error Testing

```python
import pytest

def test_raises_on_invalid_input():
    with pytest.raises(ValueError, match="must be positive"):
        calculate(-1)

async def test_async_raises():
    with pytest.raises(ConnectionError):
        await connect_to_invalid_host()
```

## Running Tests


### Reproducing CI/tox failures and detecting order coupling

When CI runs **tox**, reproduce under the same env first (pytest alone may miss dependency/async-mode differences):

```bash
tox -e py311          # pick the first failing env from CI
tox -e py311 -- -x    # stop at first failing test
tox -e py311 -- -k session -vv
```

To identify the **first causal** failure and reduce cascades:

```bash
uv run pytest -x -vv
uv run pytest --maxfail=1 --ff   # run failed tests first (order-sensitive bugs surface faster)
uv run pytest --lf -vv           # re-run last failures
```

To expose ordering dependence:
- run the failing test alone vs. full file: `pytest path::test -vv` then `pytest path -vv`
- if available, use randomized order (e.g., `pytest-randomly`) to confirm coupling

If request counts are failing, inspect and print `request_history` (or the last request JSON) to see whether setup/teardown, retries, decorators, or background flush emitted extra/missing calls.
```bash
uv run pytest -n auto              # Run all tests in parallel
uv run pytest -n auto -x           # Stop on first failure
uv run pytest path/to/test.py      # Run specific file
uv run pytest -k "test_name"       # Run tests matching pattern
uv run pytest -m "not integration" # Exclude integration tests
```

## Checklist

Before submitting tests:
- [ ] Each test tests one thing
- [ ] No `@pytest.mark.asyncio` decorators
- [ ] Imports at module level
- [ ] Descriptive test names
- [ ] Using in-memory transport (not HTTP) unless testing networking
- [ ] Parameterization for variations of same behavior
- [ ] Separate tests for different behaviors
