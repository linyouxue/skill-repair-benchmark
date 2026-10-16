# Using `--no-deps` / minimal installs safely

Use this when you ran a diagnostic install (or import smoke test) that intentionally excludes dependencies and you saw `ModuleNotFoundError`.

## What `--no-deps` is good for

- Checking *your package’s* own metadata/build steps without spending time resolving dependencies.
- Verifying that installation artifacts (dist-info, entrypoints) are created.

It is **not** representative of CI if CI installs extras and dependencies.

```python
import importlib


def smoke_import(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ModuleNotFoundError:
        return False


# Branch A: expected failure under minimal install
if not smoke_import("some_dependency"):
    diagnostic_only = True
else:
    diagnostic_only = False
```

## Runtime branches

- If CI installs full deps: ignore missing deps under `--no-deps`; do not change runtime.
- If CI uses a minimal install (rare): add guards/optional imports *and* add tests that assert the degraded behavior.

## Verification

Re-run the evaluator-equivalent install command.

- If the evaluator-equivalent install still fails: fix packaging/metadata and repeat.
- If it succeeds but runtime tests fail with missing deps: declare the dependency correctly (or make it optional *only if tests require it*), then re-run tests.
