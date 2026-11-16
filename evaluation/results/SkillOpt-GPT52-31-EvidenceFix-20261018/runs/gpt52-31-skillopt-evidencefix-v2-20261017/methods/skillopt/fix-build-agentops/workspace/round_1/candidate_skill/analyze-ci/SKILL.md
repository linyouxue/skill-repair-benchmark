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


## CI Triage Workflow (Actionable)

Use this workflow to go from failing GitHub Actions/tox output to a pinpointed root cause and a reliable local reproduction.

### 1) Find the *first causal* failure (avoid cascades)
- Prefer the **earliest, most specific assertion error** in the log (first failing test in the first failing job).
- Treat later errors as **follow-on** until proven otherwise (e.g., “session already started”, teardown errors, secondary assertion diffs).
- If multiple jobs/Python versions fail with the same symptom, **assume one shared root cause** and triage once.

Practical heuristics:
- In `pytest` output, start from the first `FAILED ...` block (not the final summary).
- Look for the first unexpected state transition, missing request, or mismatched expected/actual values.

### 2) Group failures by symptom (collapse repeats)
Across jobs/envs, group by:
- **Test file + assertion** (e.g., `tests/test_session.py::... assert 0 == 1`)
- **Common warning/error line** (e.g., “already started”, “cannot start session”, connection refused)
- **Mocking/request diffs** (e.g., request history count, endpoint/headers mismatch)

Output should explicitly say:
- “These X failures are the same root cause (repeated across py38/py39/py312).”

### 3) Reproduce locally using the same env(s)
- Re-run the same tox environment(s) shown in CI:
  - `tox -e py311` (or the failing env)
  - If many versions fail similarly, start with the **fastest** failing env.
- Isolate quickly with pytest flags:
  - `pytest -x` to stop at the first failure
  - `pytest -k <pattern>` to narrow to the failing tests
  - `pytest <path/to/test_file.py>::<test_name>` for precision

Aim: produce a **single command** that reproduces the earliest failure.

### 4) Check for state leakage / shared global state
Many multi-test failures come from one leaked singleton or background worker.
Indicators:
- Warnings like **“already started”**, “cannot start session”, “event loop is closed”, “task was destroyed but pending”
- Assertions about **extra/missing HTTP calls** (e.g., `len(request_history)` differs)
- Test order sensitivity: passing alone but failing in suite

Triage steps:
- Re-run the failing test alone vs. the full file.
- Look for module-level singletons, caches, global clients, background threads/queues not reset between tests.

### 5) Separate infra/setup issues from deterministic regressions
Classify the failure early:
- **Infra/setup**: dependency resolution, import errors, missing system libs, network flakes, timeouts, segfaults
- **Deterministic behavior regression**: assertion diffs, consistent request/response mismatches, consistent warnings

If deterministic:
- Identify the behavior change (what used to happen vs now) and locate the code path that changed.

## Checklist: Common CI-only Python Failure Patterns
- **Singleton/config contamination** across tests (module-level client, cached config, global session)
- **Background worker/queue not drained** (async tasks, threads, timers) causing late HTTP calls
- **Timing flakiness** (sleep-based assertions, race conditions) amplified on CI
- **Request-mocking mismatch** after behavior change:
  - endpoint path changed
  - header name/value changed
  - request count changed due to retries/batching
- **Asyncio mode differences** (strict mode, loop scope) causing pending tasks or fixture leakage

## What to include in the final analysis output
- Earliest failing test + assertion (the “first causal failure”)
- Grouped failure summary across jobs/envs
- Minimal local reproduction command(s) (tox + pytest)
- Likely root cause category (state leakage vs behavior regression vs infra)
- The key log snippet(s) that justify the root cause
