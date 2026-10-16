---
description: Diagnose CI failures by reproducing the evaluator install/test boundary, making minimal edits, generating valid diffs, and completing the required deliverable artifacts exactly as the evaluator expects.
---

# Analyze CI Failures

## Plan to the evaluation boundary (stop when it passes)

1. Identify the evaluator boundary: exact install command(s), toolchain versions, test invocation, and **required deliverable artifacts/paths** that decide success.
2. Record boundary constraints that change outcomes (e.g., venv vs no-venv, user-site enablement, permissions, network access).
3. Reproduce the boundary in the same mode; treat other probes (different envs, flags, or tools) as diagnostics only.
4. Target the **first hard failure** in that exact mode (permission errors, missing executables, build backend errors), not a downstream/secondary symptom.
5. Make the smallest change that could plausibly turn the boundary green.
6. Apply the change immediately (no “pending diffs”), then rerun the full boundary in the **same mode**.
7. Repeat the apply→rerun loop until the boundary is green; do not end with known red tests.
8. If the primary failure is environmental (e.g., filesystem permission denied to an install destination), explicitly conclude it is not reliably fixable from repo code and switch to making the boundary use an isolated environment only if the repo controls the entrypoint.
9. Treat deliverable generation as part of the boundary: write artifacts to the **exact required absolute paths** and verify they exist and are non-empty.
10. If any verification command errors (locale/alias/unicode flags), immediately re-run verification with simpler ASCII-only primitives (`test -s`, `wc -l`, `head`).
11. If a patch attempt fails to apply, return to a clean working tree and regenerate the patch from real edits (don’t hand-surgery hunks).

```python
from dataclasses import dataclass

@dataclass
class Boundary:
    install_cmd: str
    test_cmd: str
    required_artifacts: list[str]
    toolchain: dict
    constraints: dict

boundary = Boundary(
    install_cmd="<install command>",
    test_cmd="<test command>",
    required_artifacts=["<absolute output path>", "<absolute output path>"],
    toolchain={"pip": "<ver>", "setuptools": "<ver>"},
    constraints={"venv": "<yes/no>", "user_site": "<yes/no>", "permissions": "<notes>"},
)
```

Decision rule: If a change does not move the boundary from red to green within one apply→rerun cycle, revert or isolate it, then pursue the failing assertion/error message directly.

Read references/evaluator-equivalent-repro.md when you can’t reliably reproduce CI locally or suspect toolchain/version mismatches. Skip when you already have a container/venv that matches CI.

Read references/permission-denied-user-site.md when installs fail writing to user-site/script directories (EACCES/permission denied under a home bin path). Skip when installs happen inside an isolated venv or container with writable paths.

Read references/editable-installs-old-pip.md when CI uses `pip install -e` and errors mention `build_editable`, PEP 660, or editable fallback behavior. Skip when CI installs non-editable wheels/sdists only.

Read references/generate-valid-patches.md when you see “corrupt patch”, hunk/header mismatches, or repeated apply failures. Skip when you always patch via `git apply` from `git diff` output.

Read references/required-deliverables-at-evaluator-path.md when the task requires writing a patch/log/report to a specific absolute path or the harness says a deliverable is missing. Skip when the only success condition is passing tests.

## Triage: build/install vs runtime/test semantics

First classify the failure mode and confine changes to that layer:

- Build/install/tooling errors → change packaging/build configuration and metadata alignment.
- Runtime/test failures → change code paths exercised by the failing tests, preserving documented API semantics.

```python
def classify_failure(stderr: str) -> str:
    if any(tok in stderr for tok in ("build", "install", "backend", "wheel")):
        return "build-install"
    return "runtime-test"

layer = classify_failure("<captured stderr>")
```

Decision rule: Do not modify public API or lifecycle semantics to fix a build/install failure unless a failing test explicitly requires it.

Read references/dont-fix-build-by-changing-runtime.md when a build/install failure tempts you to change runtime imports, optional dependencies, or lifecycle behavior. Skip when CI is already past install and failing only unit tests.

## Use non-representative installs as diagnostics (don’t chase them)

Some install modes intentionally omit dependencies; missing imports there are expected and should not drive runtime changes.

```python
def is_expected_missing_deps(mode: str, exc: Exception) -> bool:
    return mode in {"no-deps", "minimal"} and isinstance(exc, ModuleNotFoundError)

mode = "<install mode>"
try:
    __import__("some_optional_dependency")
except Exception as e:
    if is_expected_missing_deps(mode, e):
        pass  # diagnostic only
```

Decision rule: Only change import/optional-dependency behavior if the evaluator uses that install mode or the tests assert behavior under missing deps.

Read references/no-deps-probes.md when you used `--no-deps`/minimal installs and saw import errors. Skip when CI installs full dependencies.

## Common Pitfalls

- Stopping after drafting a fix instead of applying it and rerunning the evaluator boundary in the same mode.
- Validating only in a convenient environment (often a fresh venv) while the evaluator fails under a different boundary (no venv, pinned tooling, restricted permissions).
- Targeting a downstream packaging symptom before the first hard failure (e.g., ignoring an EACCES/permission error during install).
- Continuing to refactor after the install/test boundary is green, causing new regressions.
- Fixing packaging/tooling problems by changing public runtime/session semantics.
- Treating missing imports from diagnostic `--no-deps`/minimal installs as evidence to change runtime behavior.
- Fixing editable-install failures by forcing legacy `setup.py develop` fallbacks that require writing to system site-packages, or by adding brittle pins on packaging tooling libraries.
- Passing tests but failing the task because a required deliverable artifact was not written to (and verified at) the evaluator’s expected absolute path.
