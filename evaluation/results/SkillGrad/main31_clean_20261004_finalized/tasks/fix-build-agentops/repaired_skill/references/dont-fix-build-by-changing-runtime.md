# Don’t fix build/install failures by changing runtime semantics

Use this when the failure happens during `pip install`/wheel build/editable install, but you’re considering changes in application code (imports, initialization, session lifecycle, etc.).

## Rule of thumb

- Build/install failures: fix **packaging/build system**.
- Runtime/test failures: fix **code**, but keep public semantics stable unless tests/documentation require a change.

```python
from dataclasses import dataclass

@dataclass
class Failure:
    phase: str  # "install" or "test"
    symptom: str


def choose_fix_surface(f: Failure) -> str:
    # Branch A: install/build phase
    if f.phase == "install":
        return "packaging"
    # Branch B: test/runtime phase
    return "runtime"


surface = choose_fix_surface(Failure(phase="install", symptom="backend missing hook"))
assert surface in {"packaging", "runtime"}
```

## Runtime branches

- If a missing optional dependency causes runtime import errors *during tests*, decide whether tests expect:
  - graceful degradation (make import optional), or
  - hard failure (keep import strict and declare dependency).
- If you only saw missing deps under a diagnostic install mode (e.g., `--no-deps`), do **not** change runtime behavior.

## Verification

1. Verify the install phase succeeds with the evaluator-equivalent toolchain.
2. Run the test suite.

If tests regress after a packaging fix:
- revert runtime/lifecycle changes first,
- then re-run tests;
- only reintroduce runtime changes if you can point to a specific failing test that requires them.
