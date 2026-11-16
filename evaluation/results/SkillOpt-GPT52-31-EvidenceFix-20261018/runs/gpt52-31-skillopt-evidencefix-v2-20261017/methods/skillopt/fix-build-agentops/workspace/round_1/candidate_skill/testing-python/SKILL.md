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

### Prefer function-scoped fixtures



### Reset shared state between tests

Libraries that manage global clients, singleton sessions, caches, background queues, or module-level config can leak state across tests and create order-dependent failures.

Use autouse fixtures or explicit teardown hooks to reset shared state:

```python
import pytest
import mylib

@pytest.fixture(autouse=True)
def reset_client_state(monkeypatch):
    # Reset singleton/session references
    mylib._client = None
    mylib._session = None

    # Clear mutable globals or cached config
    monkeypatch.setattr(mylib, "REQUEST_HISTORY", [])

    yield

    # Flush background work before next test
    if getattr(mylib, "client", None):
        mylib.client.flush()
        mylib.client.shutdown()
```

Watch for symptoms like:
- `session already started` warnings
- Request counts changing depending on prior tests
- Tags/config unexpectedly persisting between tests
- Tests passing in isolation but failing in the full suite

Prefer explicit reset helpers over hidden cached clients. Tests should control session lifecycle directly.
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



### Verify observable behavior, not implementation details

When testing telemetry, API clients, decorators, or queued background work, assert against emitted requests or recorded events instead of internal private methods.

```python
async def test_emits_single_action(mock_req, client):
    client.start_session(tags=["test"])

    await client.record_action("search")
    await client.flush()

    assert len(mock_req.request_history) == 2
    assert mock_req.last_request.json()["session"]["tags"] == ["test"]
```

If tests depend on queued uploads or async batching, expose reliable `flush()` or `wait_for_empty_queue()` helpers instead of relying on arbitrary sleeps.

Decorator-based instrumentation can also introduce duplicate or missing requests. Verify the behavioral contract explicitly:
- starting a session twice should be idempotent if intended
- repeated tag insertion should preserve deduplication behavior
- wrapped async functions should still emit events exactly once
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



## Async and decorator debugging

Avoid blocking calls such as `time.sleep()` inside async tests or async functions under test. Use async-safe coordination primitives instead:

```python
import asyncio

async def test_background_flush(client):
    await client.record("event")
    await client.flush()

    history = client.transport.request_history
    assert len(history) == 1

    await asyncio.sleep(0)
```

Decorators can change call timing, exception propagation, and request emission behavior. When debugging decorated async functions:
- verify the wrapped function is awaited correctly
- assert emitted events before and after teardown/flush
- confirm retries/background tasks are complete before assertions
- avoid timing-sensitive sleeps when explicit flush hooks or events are available
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



### Debugging order-dependent and stateful failures

If a test passes alone but fails in the suite, isolate ordering and shared-state problems first.

Useful commands:

```bash
uv run pytest --maxfail=1 --ff
uv run pytest --lf
uv run pytest -k "session or decorator"
uv run pytest tests/test_file.py::test_name -vv
```

To expose hidden coupling, run tests in different orders with plugins like `pytest-randomly`.

Common root causes:
- Singleton/session objects persisting across tests
- Module-level mutable state
- Background workers still flushing requests after a test ends
- Cached configuration or environment variables
- Mock request history not reset between tests

When debugging outbound request counts, inspect `request_history` directly and confirm whether setup hooks, retries, decorators, or teardown logic emitted additional requests.
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
