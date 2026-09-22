---
name: testing-python
description: Write and evaluate effective Python tests using pytest. Use when writing tests, reviewing test code, debugging test failures, or improving test coverage. Covers test design, fixtures, parameterization, mocking, and async testing.
---

# Writing Effective Python Tests

## Core Principles

Every test should be **atomic**, **self-contained**, and test **single functionality**. A test that tests multiple things is harder to debug and maintain.

## Debugging Test Failures (Practical Workflow)

When a build fails, prioritize **matching the verifier's test harness** and **closing the exact assertion gap**.

1. **Reproduce with the same runner/tooling**
   - If the project uses **tox**, run the failing env(s) directly (e.g. `tox -e py311`).
   - If the logs show `coverage run -m pytest`, reproduce that (coverage can change import timing and reveal state leaks).

2. **Read the failure like a contract**
   - Extract the *observable mismatch* (e.g. expected request count vs. actual, missing tags, warning emitted).
   - Tie your fix to a specific, test-observable outcome.

3. **Watch for shared state between tests**
   - Common culprits: module-level singletons, cached clients/sessions, global registries, background threads/queues.
   - If you see warnings like “already started” or behavior that depends on test order, assume **state leakage** until proven otherwise.

4. **Add/adjust resets at the correct boundary**
   - Prefer making the library behavior correct/robust (idempotent start/stop, clear session lifecycle) over changing tests.
   - If tests assume a clean global state, ensure the public API can reliably reach that state (e.g., `end_session()` truly ends, `start_session()` can start after end, tags/config persist as documented).

5. **Validate with a full run**
   - Run the whole suite (not just the one failing test) to catch regressions.

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

### Explicitly manage global/singleton state when present

If the code under test uses a module-level singleton (client/session), add explicit setup/teardown steps:

- Ensure each test starts from a known state.
- Prefer public APIs for reset/stop; if none exist, consider adding a safe reset hook in the library.
- Symptoms that indicate missing reset:
  - warnings like “session already started”
  - request counts depending on test order
  - missing/old config leaking into later tests

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

```bash
uv run pytest -n auto              # Run all tests in parallel
uv run pytest -n auto -x           # Stop on first failure
uv run pytest path/to/test.py      # Run specific file
uv run pytest -k "test_name"       # Run tests matching pattern
uv run pytest -m "not integration" # Exclude integration tests
```

### If the project uses tox/coverage, mirror it

```bash
# Run a specific tox env that matches CI
tox -e py311

# Or mirror the exact command shown in CI logs
coverage run --source <package> -m pytest
coverage report -m
```

## Checklist

Before submitting tests or fixes:
- [ ] I reproduced failures with the same harness (tox/coverage/pytest flags) used by CI
- [ ] Each test tests one thing
- [ ] No `@pytest.mark.asyncio` decorators (unless project explicitly requires it)
- [ ] Imports at module level
- [ ] Descriptive test names
- [ ] Using in-memory transport (not HTTP) unless testing networking
- [ ] Parameterization for variations of same behavior
- [ ] Separate tests for different behaviors
- [ ] If failures suggest state leakage ("already started"), I verified singleton/session lifecycle correctness
