---
name: testing-python
description: Write and debug Python tests with pytest (unit/integration, fixtures, mocking, async). Use when adding coverage or diagnosing failing tests.
---

# Testing Python with pytest (high-signal)

Keep tests **small**, **deterministic**, and **easy to debug**. Prefer verifying one behavior per test.

## Fast triage when tests fail

```bash
# If `pytest` isn’t on PATH:
python -m pytest

# Run a single test (node id)
pytest path/to/test_file.py::TestClass::test_case -q

# Only failures from last run
pytest --lf -q

# Stop after first failure (faster feedback)
pytest -x

# Filter by substring
pytest -k "login and not slow" -q

# More detail
pytest -vv
```

Tips:
- Start by reproducing **one** failure locally.
- Read the assertion diff and traceback *before* changing code.

## Writing effective tests

### Arrange → Act → Assert

```python
def test_uppercases_ascii_letters():
    # Arrange
    s = "hello"

    # Act
    out = s.upper()

    # Assert
    assert out == "HELLO"
```

### Parameterize variations of the same behavior

```python
import pytest

@pytest.mark.parametrize(
    "s,expected",
    [("hello", "HELLO"), ("World", "WORLD"), ("", ""), ("123", "123")],
)
def test_upper_is_idempotent_for_non_letters(s, expected):
    assert s.upper() == expected
```

## Fixtures

Use fixtures to share setup **without** coupling tests.

- Default to **function-scoped** fixtures.
- Use `tmp_path` for filesystem interactions.

```python
import pytest

@pytest.fixture
def tmp_config(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"enabled": true}')
    return p

def test_reads_config_file(tmp_config):
    assert tmp_config.read_text() == '{"enabled": true}'
```

## Mocking

Mock at the **boundary** (network calls, subprocesses, time, randomness).

- `unittest.mock.patch` works everywhere.
- If the repo uses `pytest-mock`, prefer the `mocker` fixture.

```python
from unittest.mock import patch

def test_fetch_uses_timeout():
    with patch("mymodule.requests.get") as get:
        get.return_value.status_code = 200
        mymodule.fetch("https://example.com")
        get.assert_called_once()
```

## Async tests (don’t assume project settings)

Different repos configure async testing differently.

- If using **pytest-asyncio**, check `pytest.ini` or `pyproject.toml` (`[tool.pytest.ini_options]`) for `asyncio_mode`.
  - If `asyncio_mode = auto`, `async def test_...` usually works without decorators.
  - Otherwise, you typically need `@pytest.mark.asyncio`.

When in doubt, mirror the style already used in the existing test suite.

## Optional: coverage / xdist

Only use these if the repo has the plugins installed.

```bash
pytest --cov=yourpkg --cov-report=term-missing
pytest -n auto
```

## Checklist

- [ ] Each test asserts one behavior
- [ ] Tests do not depend on network / wall clock time
- [ ] Good names: failing test tells you what broke
- [ ] Uses fixtures for shared setup; no hidden global state
- [ ] Async style matches repo configuration
