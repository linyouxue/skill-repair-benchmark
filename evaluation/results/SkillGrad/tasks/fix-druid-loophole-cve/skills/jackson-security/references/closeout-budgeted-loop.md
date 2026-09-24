# Budgeted deliverable-first closeout loop

Use this chapter to prevent “empty output inventory” failures on repair/hardening tasks with strict deliverables (patch files + diff/commit + build/test proof).

## Runnable procedure (tool-call budget aware + deadloop detection)

```python
from dataclasses import dataclass

@dataclass
class State:
    tool_calls: int = 0
    artifacts_exist: bool = False
    diff_non_empty: bool = False
    build_green: bool = False
    # "Progress" means: you learned a new concrete repo location (file path + symbol)
    # OR you produced a concrete diff plan.
    last_action_made_progress: bool = True
    same_non_progress_streak: int = 0


def early_checkpoint_exceeded(state: State, max_calls_without_artifact: int = 5) -> bool:
    return (not state.artifacts_exist) and state.tool_calls >= max_calls_without_artifact


def pivot_checkpoint_exceeded(state: State, max_calls_without_artifact: int = 10) -> bool:
    return (not state.artifacts_exist) and state.tool_calls >= max_calls_without_artifact


def definition_of_done(state: State) -> bool:
    return state.artifacts_exist and state.diff_non_empty and state.build_green


def next_step(state: State) -> str:
    # Deadloop guard: repeating non-progress patterns is worse than writing a minimal patch.
    if (not state.last_action_made_progress) and state.same_non_progress_streak >= 2:
        return "FORCE_PIVOT_TO_ONE_OF:SEARCH_OR_WRITE_PATCH_OR_RUN_BUILD"

    # Branch A: no artifact yet → force creation immediately
    if not state.artifacts_exist:
        if early_checkpoint_exceeded(state):
            return "WRITE_MINIMAL_PATCH_ARTIFACT_NOW"
        if pivot_checkpoint_exceeded(state):
            return "WRITE_MINIMAL_PATCH_ARTIFACT_NOW"
        return "CREATE_PATCH_DIR_AND_WRITE_SKELETON_ARTIFACT"

    # Branch B: artifact exists but no code change → ensure diff/commit exists
    if state.artifacts_exist and not state.diff_non_empty:
        return "MAKE_MINIMAL_CODE_CHANGE_OR_ADD_FAILING_TEST"

    # Branch C: code change exists but build/test not green → iterate only on build failures
    if state.diff_non_empty and not state.build_green:
        return "RUN_REQUIRED_BUILD_OR_TEST_AND_FIX_ERRORS_ONLY"

    return "DONE"


# Verification harness: ensure we never advise looping on non-progress.
s = State(tool_calls=9, artifacts_exist=False, diff_non_empty=False, build_green=False,
          last_action_made_progress=False, same_non_progress_streak=2)
assert next_step(s) == "FORCE_PIVOT_TO_ONE_OF:SEARCH_OR_WRITE_PATCH_OR_RUN_BUILD"
```

## How to apply it (mapping to real actions)

- `CREATE_PATCH_DIR_AND_WRITE_SKELETON_ARTIFACT`: create the required output directory and write at least one patch file immediately (even if it’s a minimal hardening change or a regression test stub).
- `WRITE_MINIMAL_PATCH_ARTIFACT_NOW`: stop investigating; implement the smallest safe change you can justify (prefer adding validation / tightening configuration / adding a regression test) and write the patch file.
- `MAKE_MINIMAL_CODE_CHANGE_OR_ADD_FAILING_TEST`: ensure `git diff` is non-empty (or commit). If you can’t find root cause quickly, add a regression test capturing the vulnerability.
- `RUN_REQUIRED_BUILD_OR_TEST_AND_FIX_ERRORS_ONLY`: run the exact required command; only iterate on compilation/test failures until green.
- `FORCE_PIVOT_TO_ONE_OF:SEARCH_OR_WRITE_PATCH_OR_RUN_BUILD`: pick exactly one pivot:
  1) `SEARCH`: run a repo search to find the entrypoint (file path + symbol) for parsing/config/loading.
  2) `WRITE_PATCH`: write the minimal patch/test artifact now.
  3) `RUN_BUILD`: run the required build/test to get actionable errors.

## Runtime branch (when build remains red)

If the required build/test command keeps failing:
- **Branch 1 (fast fixable):** failures are missing imports, compilation errors, formatting, or test assertions → fix directly and rerun.
- **Branch 2 (unclear / rabbit hole):** failures indicate broader refactors or environment issues → revert to the minimal patch/test you already wrote and make it compile; do not expand scope.

## Verification step (and corrective action)

After each 1–2 tool calls, re-check the definition of done *and* the deadloop guard:
- If you have **no patch artifact**, immediately execute `WRITE_MINIMAL_PATCH_ARTIFACT_NOW`.
- If your last actions are **not producing new repo locations or a diff plan**, execute `FORCE_PIVOT_TO_ONE_OF:SEARCH_OR_WRITE_PATCH_OR_RUN_BUILD` (and do not repeat the prior non-progress action).
- If **`git diff` is empty**, execute `MAKE_MINIMAL_CODE_CHANGE_OR_ADD_FAILING_TEST`.
- If **build/test is not green**, execute `RUN_REQUIRED_BUILD_OR_TEST_AND_FIX_ERRORS_ONLY`.

Stop only when all three gates are satisfied.
