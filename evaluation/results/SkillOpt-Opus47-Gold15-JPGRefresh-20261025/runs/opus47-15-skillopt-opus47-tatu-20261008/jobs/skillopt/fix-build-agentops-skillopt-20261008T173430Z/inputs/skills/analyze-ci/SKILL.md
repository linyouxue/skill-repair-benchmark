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


## Build-Repair Workflows

When using this skill as part of a build-repair task (verifier runs the full build/test suite and any failing test fails the task), follow these rules:

1. **Enumerate every failure.** Scan the entire log for every failing test/job, not just the first `ImportError`/`ModuleNotFoundError`/collection error. Collection errors often mask additional runtime/assertion failures that surface once imports are fixed.
2. **Never dismiss remaining failures as "pre-existing", "flaky", "unrelated", or "out of scope"** unless the verifier/task explicitly excludes them. The verifier typically re-runs the full suite via the project's own build script (e.g. `tox`, `run_passed.sh`), and any non-zero exit code or any `FAILED` line fails the build.
3. **Iterate until green.** After each fix, re-run the full build script (not just a single test file). Continue fixing until exit code is `0` AND the pytest summary shows `0 failed`. Consider: tightening timing-sensitive assertions, patching flaky tests, mocking unstable sources, or adjusting the code under test.
4. **Recognize build pass vs fail.** A build passes only when:
   - the top-level build/test command exits `0`,
   - the pytest summary line reads e.g. `N passed` with no `failed`/`error` counts,
   - no `##[error]Process completed with exit code N` line appears in CI logs.
   A single `FAILED tests/...` line means the build is still broken, even if most tests pass.
