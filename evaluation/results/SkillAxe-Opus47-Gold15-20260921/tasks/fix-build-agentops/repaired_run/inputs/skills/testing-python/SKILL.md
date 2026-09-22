---
name: testing-python
description: Write and evaluate effective Python tests using pytest, and reproduce/fix build failures against the project's own declared test runner (tox, nox, make, uv, pytest). Use when writing tests, reviewing test code, debugging test failures, fixing failed builds, or improving test coverage. Covers test design, fixtures, parameterization, mocking, async testing, and verifier-parity reproduction of CI/build failures.
---

# Writing Effective Python Tests

## Core Principles

Every test should be **atomic**, **self-contained**, and test **single functionality**. A test that tests multiple things is harder to debug and maintain.

## Reproducing Build / CI Failures (read this first when fixing a failed build)

When the task is "fix the build" or "make CI pass", the definition of success is **the project's own declared runner exits 0**, not `pytest` from an ad-hoc venv. Before editing anything, and again before declaring the task done, reproduce the failure using the same runner the verifier/CI uses.

### Runner discovery checklist

Inspect the repo root for the authoritative runner, in this order:

1. `tox.ini` or `[tool.tox]` in `pyproject.toml` → run `tox` (or `tox -e <env>`). The `envlist` defines every environment that must pass.
2. `noxfile.py` → run `nox`.
3. `Makefile` targets like `test`, `check`, `ci` → run those.
4. `.github/workflows/*.yml` → read the exact command the CI job runs (`run:` steps). Mirror it locally.
5. `pyproject.toml` `[tool.pytest.ini_options]` or `pytest.ini` → only fall back to bare `pytest` if nothing above exists.

If you only run bare `pytest` against a hand-picked interpreter, you can miss:
- Environments in the tox `envlist` whose Python interpreter is not installed (e.g. `py37: could not find python interpreter matching any of the specs py37`). These count as build failures.
- Plugins loaded only inside the tox env (e.g. `pytest-asyncio`, `requests_mock`) that change which tests are collected, skipped, or executed.
- Version-pinned dependencies in `[testenv].deps` or `install_package_deps` that produce different behavior than your interactive venv.

### Verifier-parity rules

- **Do not classify any failing test as "pre-existing" or "out of scope" for a build-fix task.** If the runner exits non-zero, the build is failing and the task is not done. Investigate the failure and fix it in code or configuration (skip markers, xfail with reason, dependency pin, environment guard, or a real code fix — pick the minimal correct option).
- **Reproduce with the same interpreter matrix the runner uses.** If `tox -l` lists `py37,py38,py39,py310,py311,py312` and only 3.10/3.11/3.12 are installed on the runner, either install the missing interpreters or narrow `envlist`/use `tox --skip-missing-interpreters=true` — whichever matches how the verifier is configured. Read the CI workflow to decide; do not guess.
- **Do not stop at "tests collect successfully".** Collection succeeding is necessary but not sufficient. The runner must exit 0.
- **Beware of silently-skipped tests.** A test that is skipped in your local venv (e.g. `async def` skipped because `pytest-asyncio` is not installed) will run and can fail under tox where the plugin is declared. Always match the plugin set from `[testenv].deps`.

### Failure-triage order (build-fix tasks)

1. Run the declared runner, capture full output.
2. For each failing environment, categorize the failure:
   - **Environment/config**: missing interpreter, missing dependency, wrong pin, wrong build backend. Fix in `tox.ini`, `pyproject.toml`, workflow file, or by installing the interpreter.
   - **Import-time failure**: optional dependency imported unconditionally. Guard with `try/except ImportError` at the import site, or move the import into the extra's own module and only expose it when installed.
   - **Real test logic failure**: fix the underlying code (or, if the test itself is wrong and the runner is authoritative, fix the test). Do not merely mask with `@pytest.mark.skip` unless justified in a comment and matched by CI expectations.
3. After each edit, rerun the declared runner (not bare pytest) and confirm exit 0 across the full env matrix.

### Common concrete patterns

- **Optional import at package `__init__`**: wrap in `try/except ImportError` so the base package imports without the extra, but keep the symbol exported when the extra is installed.
- **`tox` cannot find `py37`/`py38`/`py39` on modern runners**: either (a) add `skip_missing_interpreters = true` to `[tox]` if the CI job also sets it, (b) trim `envlist` to the interpreters actually available in the CI image, or (c) install the missing interpreters via `actions/setup-python` matrix / `uv python install`. Match the CI workflow's real intent.
- **Timestamp / timing tests that assert `init_timestamp != end_timestamp`**: these fail deterministically when the timestamp helper truncates to millisecond precision and the event constructor + `record()` land in the same millisecond. Fix the helper (higher precision, monotonic sequence, or explicit sleep in `record()`), not the test — the test encodes the real invariant.

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

These rules apply when the project you are working on declares them (e.g. via `pyproject.toml`, contribution docs, or fixture setup). They are not universal — read the target project's conventions first.

### `asyncio_mode = "auto"`

If the project sets `asyncio_mode = "auto"` globally, write async tests without decorators:

```python
# Correct (when asyncio_mode = "auto")
async def test_async_operation():
    result = await some_async_function()
    assert result == expected

# Wrong under asyncio_mode = "auto"
@pytest.mark.asyncio
async def test_async_operation():
    ...
```

If the project does NOT set auto mode, `pytest-asyncio` requires `@pytest.mark.asyncio` (or install a compatible plugin). An async test with neither is silently skipped by plain pytest — do not mistake that skip for success.

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
```

### Use in-memory transport for testing (fastmcp-style projects)

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

## Running Tests

Prefer the project's declared runner. Common invocations:

```bash
# Project uses tox — this is the source of truth for CI
tox                                # run full envlist
tox -e py311                       # single env
tox -l                             # list envs the project declares
tox --skip-missing-interpreters=true  # if CI also skips missing

# Project uses nox
nox
nox -s tests

# Project uses uv
uv run pytest
uv sync --all-extras --dev && uv run pytest

# Bare pytest (only when the project has no higher-level runner)
pytest -n auto              # Run all tests in parallel
pytest -n auto -x           # Stop on first failure
pytest path/to/test.py      # Run specific file
pytest -k "test_name"       # Run tests matching pattern
pytest -m "not integration" # Exclude integration tests
```

Always read `.github/workflows/*.yml` to confirm the exact command CI runs, and mirror it locally before declaring a build-fix task complete.

## Checklist

Before submitting tests:
- [ ] Each test tests one thing
- [ ] Async decorator matches project's `asyncio_mode` setting
- [ ] Imports at module level
- [ ] Descriptive test names
- [ ] Parameterization for variations of same behavior
- [ ] Separate tests for different behaviors

Before declaring a build-fix task done:
- [ ] Identified the project's real test runner (tox / nox / make / uv / pytest)
- [ ] Ran that runner and captured the failing envs
- [ ] Every env in the runner's matrix exits 0 (not just "pytest passes on my venv")
- [ ] No failure was dismissed as "pre-existing" or "out of scope" without a code-level fix, a justified skip/xfail, or a config change that matches CI
- [ ] Missing interpreters in the tox matrix are either installed or excluded in a way consistent with the CI workflow
