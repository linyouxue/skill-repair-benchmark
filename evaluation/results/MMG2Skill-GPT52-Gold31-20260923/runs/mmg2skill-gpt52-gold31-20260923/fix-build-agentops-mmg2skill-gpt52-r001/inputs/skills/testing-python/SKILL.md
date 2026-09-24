---
name: testing-python
description: Debug and fix Python test failures using pytest with disciplined isolation,
  minimal changes, and regression prevention.
---

## Steps
1. Reproduce the failure locally with `pytest -x` (or a targeted file/test via `pytest path/to/test.py -k name`).
2. Read the failing assertion/traceback carefully and identify the exact behavior mismatch (not just the symptom).
3. Locate the responsible code path by searching for referenced functions/classes/log strings (use `rg`, or `grep -R` if `rg` is unavailable).
4. Implement the *smallest* behavior change that satisfies the failing test **without** changing public lifecycle semantics that other tests rely on.
   - In particular, avoid “helpful” implicit behavior in global entry points (e.g., auto-starting sessions in `init()`), because it can create cross-test state and break expectations.
   - If failures relate to global/singleton state, prefer resetting/clearing state at the correct boundary (or making operations no-op-safe) rather than starting work implicitly.
5. Validate against regressions:
   - Run the originally failing test(s).
   - Then run the full suite to ensure no new failures/warnings were introduced (watch for repeated warnings indicating state leakage).
6. When preparing patch files, generate diffs from the repo to avoid corrupt hunks:
   - Make edits normally, then use `git diff > patch_1.diff` (or similar) so headers/hunk counts are correct.
   - Optionally sanity-check with `git apply --check patch_1.diff` before applying.
## Expected Result
A fix that makes the failing test(s) pass while keeping the rest of the suite stable (no new failures due to singleton/stateful side effects), delivered as valid unified diffs.
