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

### L2: Evaluator-signal anchoring (CI-path first)

When diagnosing a failure, **anchor on the evaluator/CI pathway signal**:

1. **Start from the failing job(s) and failing command(s)** in the matrix (e.g., specific tox env / Python version) and extract:
   - failing test file(s) + assertion text
   - stack trace or error type
   - any version-dependent pattern (e.g., py310 passes, py311/py312 fail)
2. Treat local environment friction (editable install quirks, permissions, stale tooling) as **secondary** unless it reproduces the same failure mode in the same pathway.
3. If the failure is matrix-specific, **reproduce the failing env(s)** before proposing a root cause.

**Verification gate / fallback**
- After each candidate fix, rerun the same CI-path check that failed (at minimum the failing tox env(s); ideally the full matrix). If a patch fixes only a local setup issue but the CI-path tests still fail, discard that hypothesis and return to the failing tests/logs.

## Examples

```bash
# Analyze CI failures for a PR
uv run skills analyze-ci https://github.com/mlflow/mlflow/pull/19601

# Analyze specific job URLs directly
uv run skills analyze-ci https://github.com/mlflow/mlflow/actions/runs/12345/job/67890
```
