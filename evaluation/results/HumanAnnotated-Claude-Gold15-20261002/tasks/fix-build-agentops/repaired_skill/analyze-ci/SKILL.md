---
name: analyze-ci
description: Analyze failed GitHub Action jobs or reproduce and repair a provided local CI build.
allowed-tools:
  - Bash(uv run skills analyze-ci:*)
---

# Analyze CI Failures

This skill analyzes logs from failed GitHub Action jobs using Claude.


## Local repository build repair

Use this workflow when a local failing checkout is provided. The requested outcome is the configured CI build passing, including its unit-test assertions. A test already failing in the starting checkout is part of the repair scope. Remote analysis below applies only to supplied PR/job URLs.

### Establish the reproduction
Identify the checkout by source plus build configuration; a neighboring virtual environment is tooling, not another broken project unless the workflow references a failing operation in it. Read the CI and test-runner configuration and run its configured dependencies and tests. In a Python project, compare an ad-hoc dev install with the testenv dependencies before diagnosing a missing optional package as the original CI failure. Preserve the command's actual exit code (pipefail or PIPESTATUS when piping logs).

### Continue from every remaining failure
After a patch, run the required suite and put each remaining failure in the diagnostic note: exact command/environment, assertion or setup error, relevant warning, hypothesis, next discriminating check, and observed result. Repeat the following loop before preparing the final summary:

1. Run a failing test alone in a fresh Python process, then in the suite. For pytest, use the observed node ID with -vv and --tb=long, saving the full output. Claim test-order contamination only if the isolated and suite results differ under the same environment; otherwise investigate the failure that reproduces in isolation.
2. Follow the actual execution path from test setup to the failed assertion. When a warning reports an early return, inspect the guard and the operation that should have established its precondition. Check state immediately before/after that operation and inspect any caught exception or failed setup. A correct downstream helper cannot explain behavior on a path that never reached it.
3. Compare the observation with the hypothesis, fix the source/configuration cause, and run the isolated test plus the full suite again. A speculation about singleton state, timing, or a test bug is not a finding until a discriminating check supports it. Fix the earliest broken state transition rather than bypassing its guard, weakening an assertion, or changing expected behavior to match the broken output.
4. Keep an executed assertion failure open even when it predates the first import fix. Import/collection success plus failing tests still means the build fails. Finish only when the failure ledger has no unresolved required code/test failures; if genuinely blocked by unavailable infrastructure, report that exact unverified condition separately.

### Deliver and verify
Generate standard unified patches from the actual edits, check clean application to the starting checkout, and keep the applied source and requested notes consistent with them. Run the configured build after the final patch and record executed environments, real exit codes and test results. Distinguish interpreter/dependency setup failures from executed assertions; preserve required coverage and justify any supported-version configuration change from public project constraints. A final note that calls remaining test failures 'pre-existing' or 'out of scope' does not complete a request to repair the build.

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
