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
async def test_async_operation():
    result = await some_async_function()
    assert result == expected
```

### Imports at module level

Put imports at the top of the file unless the project explicitly requires a delayed import.

### Use in-memory transport for testing

Mock external boundaries rather than internal code when isolation is required.

## Running Tests

```bash
uv run pytest -n auto
uv run pytest -n auto -x
uv run pytest path/to/test.py
uv run pytest -k "test_name"
uv run pytest -m "not integration"
```

## Regression Gate for Stateful SDK Repairs

For packages with module-level clients, singletons, sessions, workers, decorators, request queues, mutable event objects, or other process-shared state, a test that passes alone can still fail in sequence. Treat order sensitivity as diagnostic evidence, not as proof that global lifecycle construction is itself wrong.

1. Record the authoritative baseline before editing: exact failing node IDs, pass/fail counts, exception classes, and the assertion contract. If the original suite is already at `9 passed, 1 failed`, preserve that state as the minimum acceptable regression baseline until the remaining failure is fixed.
2. Reproduce one failing test in isolation, then run the containing module and the full configured suite. A fix is not accepted if it repairs one assertion while creating a new failure or error elsewhere.
3. If isolated and suite results differ, build a lifecycle table for uninitialized, active, ended, and reused states. Inspect singleton instances, ended sessions, cached configuration, accumulated tags, background workers, request history, and mutable objects. However, **sequence dependence only proves that shared state influences the symptom; it does not prove that singleton identity, cache reset policy, or object reconstruction is the repair target.**
4. Start from the failing assertion's owning object and transition. For assertions about timestamps, completion flags, statuses, result values, mutation, or serialization, inspect that object's initialization semantics and the code path that updates it before changing process-global lifecycle behavior.
5. Preserve the public lifecycle contract at the module boundary. Trace `init`, `start_session`, `record`, decorators, `end_session`, and teardown through the existing singleton semantics. Do not change singleton creation/reuse semantics merely to make one test start from a fresh object unless the API contract and authoritative failure evidence specifically require that behavior.
6. Treat changes to singleton identity, cache construction, automatic restart, or global reset behavior as high-risk. Immediately run the full relevant suite after such a candidate. If it creates a new exception class, a new failing node, or fewer passing tests, revert it before investigating anything else.
7. Use a minimal state-transition fix at the component that owns the violated contract. Prefer correcting the object's initialization/update semantics over broad packaging, dependency, fixture, or lifecycle changes when the failure is a field-transition assertion.
8. After every candidate patch, compare the exact failure set with the last-known-good snapshot. Restore a regression before trying the next hypothesis instead of stacking more changes onto it. Never patch a newly introduced regression while retaining the candidate that caused it.
9. Run the exact project command under the dependency constraints and environment used by CI. Isolated tests are diagnostic evidence; completion requires the full authoritative suite to pass in the runtimes actually exercised by the benchmark.

### Stateful failure decision rule

Use this order before modifying global lifecycle code:

1. What exact assertion failed?
2. Which object owns the asserted field/behavior?
3. What should that object's state be at construction?
4. Which operation is supposed to transition that state?
5. Does the failure reproduce without changing singleton/cache identity?
6. Only if the contract itself requires a new/reinitialized global object should singleton/reset semantics be changed.

## Checklist

Before submitting a repair:
- [ ] Baseline failing node IDs and counts recorded
- [ ] Exact failing assertion understood
- [ ] Narrow test rerun after each candidate
- [ ] Full relevant suite rerun after each candidate
- [ ] No newly introduced failing node or exception class retained
- [ ] Global singleton/cache semantics unchanged unless directly justified
- [ ] Final patch corresponds exactly to the working tree that passed
