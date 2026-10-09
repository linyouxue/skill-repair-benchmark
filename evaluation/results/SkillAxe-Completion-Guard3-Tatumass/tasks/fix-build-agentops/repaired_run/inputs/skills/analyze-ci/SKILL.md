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

## How to Use the Output (for build-fix tasks)

When you get a CI failure summary, immediately convert it into a local reproduction plan:

1. **Identify the harness**
   - Does CI run `tox`, `nox`, `pytest`, or a custom script?
   - Does it run under `coverage run -m pytest`?

2. **Pin the failing environment**
   - Note the Python version(s) that fail and those that pass.
   - If only some versions fail, suspect version-conditional behavior (stdlib changes, typing, event loop policy, etc.).

3. **Extract the smallest observable mismatch**
   - Assertion diffs (expected vs actual)
   - Warnings that indicate state leakage (e.g., “already started”)
   - Counts/timing issues (e.g., expected 2 requests but saw 1)

4. **Verify after every fix**
   - Re-run the same CI command locally (or as close as possible) before moving on.

This prevents spending iterations on unrelated environment issues when the verifier is failing in runtime tests.

## Examples

```bash
# Analyze CI failures for a PR
uv run skills analyze-ci https://github.com/mlflow/mlflow/pull/19601

# Analyze specific job URLs directly
uv run skills analyze-ci https://github.com/mlflow/mlflow/actions/runs/12345/job/67890
```
