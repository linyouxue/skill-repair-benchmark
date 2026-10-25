---
name: analyze-ci
description: Analyze failed GitHub Action jobs for a pull request.
allowed-tools:
  - Bash(uv run skills analyze-ci:*)
---

# Analyze CI Failures

This skill analyzes logs from failed GitHub Action jobs using Claude.

## Prerequisites

- **GitHub Token**: Auto-detected via `gh auth token`, or set `GITHUB_TOKEN` env var

## Usage

```bash
# Analyze all failed jobs in a PR
uv run skills analyze-ci <pr_url>

# Analyze specific job URLs directly
uv run skills analyze-ci <job_url> [job_url ...]

# Show debug info (tokens and costs)
uv run skills analyze-ci <pr_url> --debug
```

Output: A concise failure summary with root cause, error messages, test names, and relevant log snippets.

## Examples

```bash
# Analyze CI failures for a PR
uv run skills analyze-ci https://github.com/mlflow/mlflow/pull/19601

# Analyze specific job URLs directly
uv run skills analyze-ci https://github.com/mlflow/mlflow/actions/runs/12345/job/67890
```


## Build-Repair / BugSwarm Mode

When this skill is used inside a build-repair task (e.g. BugSwarm, where the repo lives at `/home/github/build/failed/<repo>/<id>` and a verifier re-runs the project's own build), the GitHub-Actions PR log flow above does NOT apply. Instead:

1. **Locate the local build entrypoint.** Look in the repo for the ground-truth build command, in this priority order:
   - `run_failed.sh` / `run_passed.sh` (BugSwarm convention — these are the exact scripts the verifier runs)
   - `tox.ini` (run `tox` with no args, or the specific env the script invokes)
   - `noxfile.py`, `Makefile` targets like `test`/`check`
   - `Dockerfile` / `.github/workflows/*.yml` build+test steps
   Run that entrypoint end-to-end. Do NOT substitute `pytest tests/` for the real script — tox/nox often set env vars, install extras, and run coverage that change outcomes.

2. **Oracle diff (REQUIRED when a passing reference exists).** BugSwarm tasks ship both a failed and a passed image/snapshot. Before deciding any failure is "out of scope":
   - Run the oracle/passing build (e.g. `run_passed.sh` on the passed snapshot, or inspect `/home/github/build/passed/...`).
   - Collect its full list of passing tests.
   - Diff against the current failing run. **Any test that passes in the oracle but fails now is in-scope and MUST be fixed.** Only tests that also fail in the oracle may be considered pre-existing.

3. **Definition of green.** The build is fixed only when ALL of the following hold on the full build script:
   - Top-level command exits with code `0`.
   - Pytest summary reports `0 failed` and `0 errors` (skips/xfails are OK).
   - No `##[error]Process completed with exit code N` line in the log.
   A single `FAILED tests/...` line = still broken, even if 99% pass.

4. **Do not rely on heuristic labels.** Phrases like "flaky", "unrelated", "pre-existing", or "out of scope for a build fix" are NOT acceptable justifications for leaving a failure. Verify via the oracle diff in step 2. If the oracle passes that test, the failure is in-scope — investigate the production code (timing precision, deprecated APIs, missing attrs, etc.), not just the test.

5. **Iterate.** After each patch, re-run the full build entrypoint from step 1 and re-check step 3. Continue until green.
