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


## Debugging Timing-Sensitive Test Failures

When a test asserts that two timestamps differ (e.g. `assert event.init_timestamp != event.end_timestamp`) and fails with **equal values** after a `sleep`, this is a **real bug**, not a flake. Do not dismiss it as "pre-existing" or "unrelated" — if the build/verifier runs this test, you must fix it.

The fix almost always belongs in the **production helper that generates the timestamp**, not in the test. Investigate in this order:

1. **Precision/truncation in the helper.** Check for `isoformat(timespec='milliseconds')` or `'seconds'`. If `sleep` duration (e.g. `0.15s` = 150ms) is near or below the precision window, two calls can produce identical strings. Prefer `timespec='microseconds'`.
2. **Deprecated datetime APIs.** `datetime.utcfromtimestamp(...)` is deprecated. Replace with timezone-aware `datetime.now(timezone.utc)` (and format accordingly). A `DeprecationWarning` in the captured output is a strong hint.
3. **Sleep vs. precision window.** Confirm the test's `sleep` is longer than the helper's resolution. If not, either increase precision or (less preferred) use `time.monotonic_ns()` for ordering.
4. **Monotonicity.** If strict ordering matters, back the helper with a monotonic counter or `time.perf_counter_ns()` so repeated rapid calls are guaranteed distinct.

Example fix pattern (in `helpers.py`, not the test):

```python
# Before (deprecated + millisecond truncation causes equal timestamps)
return datetime.utcfromtimestamp(time.time()).isoformat(timespec='milliseconds') + 'Z'

# After
return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
```

**Rule of thumb:** if a test asserts "A happened before B" and the assertion fails because the recorded times are equal, the recorder is lossy — fix the recorder.

## Running Tests

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


- [ ] Timestamp-equality failures investigated as source-helper bugs (precision, deprecated `utcfromtimestamp`), not dismissed as flakes
