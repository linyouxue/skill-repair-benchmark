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



## Failure Classification and Evidence Boundaries

Start with the earliest failing log step, not the final propagated error. Classify the failure before proposing a repository change:

1. **Repository code**: project files, tests, imports, configuration, or commands fail after the repository has been fetched and execution has begun.
2. **Python dependencies or environment**: package resolution, installation, interpreter-version constraints, virtual-environment setup, or dependency imports fail after the build environment is available.
3. **Container build**: Dockerfile instructions, local build scripts, or project packaging steps fail after the base image and required build context have been retrieved.
4. **External infrastructure**: image metadata or layer pulls, Docker registry authentication, DNS, proxy access, network connectivity, or request timeouts fail before project execution.

Treat Docker Hub token requests, base-image metadata or pulls, registry authentication, DNS/proxy errors, and network timeouts that occur before project files execute as environment or registry failures, not source defects. Report the exact failing endpoint and earliest step, and recommend appropriate reproducibility and connectivity checks (for example, retrying the same command, checking registry access/authentication, DNS resolution, proxy configuration, and timeout behavior) rather than inventing a code fix. Do not modify repository code to compensate for an unavailable external service unless later logs show an independent repository failure.

A GitHub job or run diagnosis requires accessible GitHub Actions logs (obtained from the supplied job/run URL or PR and authenticated as needed). If only local Docker or container-build evidence is available, state that GitHub job analysis could not be confirmed and do not present the local infrastructure failure as a repository fix. If later logs show project execution and a separate source or dependency error, analyze that later error independently while preserving the earlier infrastructure classification.
