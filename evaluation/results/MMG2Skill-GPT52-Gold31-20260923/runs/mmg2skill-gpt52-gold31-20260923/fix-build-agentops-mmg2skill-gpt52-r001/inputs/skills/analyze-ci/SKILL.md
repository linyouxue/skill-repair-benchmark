---
name: analyze-ci
description: Analyze CI/test failures and extract the actionable root cause and next
  steps.
allowed-tools:
- Bash(uv run skills analyze-ci:*)
---

## Steps
1. Gather failure artifacts (GitHub Actions job logs when available; otherwise local `pytest`/build output).
2. Identify the *first* real error (exception/traceback) and note the failing test names/files and any repeated warnings.
3. Correlate failures to code by searching the repo for key symbols/strings from the traceback/logs.
   - Prefer `rg` if available; if not, fall back to `grep -R "pattern" -n .`.
4. Produce a concise summary: failing tests, exact error messages, suspected component(s), and a minimal plan to confirm/fix.
5. After applying a fix, re-run the relevant subset of tests first (single file / `-k`), then re-run the full suite to ensure no regressions.
## Expected Result
A clear root-cause statement plus a minimal, test-verified plan that avoids introducing new failures.
