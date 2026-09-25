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

## Local or Reproduced CI Failures

When the task provides a failed repository and a local CI/reproducer script instead of a PR URL, treat the captured CI artifacts and the provided reproducer as the authoritative build contract.

1. Before constructing any new local reproduction, inspect all available captured CI artifacts and original build logs, including files such as `*-orig.log`, workflow output, and reproducer logs. Record the earliest concrete failing command, failing test node IDs, pass/fail counts, and runtime version(s). If the captured CI reaches pytest/tox and reports a specific code-level failure, that failure is the baseline even if a newly constructed local environment later exposes unrelated packaging or installation problems.
2. Preserve the original repository state and inspect the build workflow, package metadata, test configuration, runtime constraints, and the exact failing command before editing.
3. Run the narrowest faithful reproduction of the captured failure first. Do not replace an existing authoritative failure with an easier-to-trigger command such as an editable install unless that exact command is part of the recorded CI path.
4. Separate actionable product failures from infrastructure limitations. Missing interpreters, unavailable services, package-index failures, permissions, and sandbox-specific installer behavior are not evidence that packaging, tox, workflow, or product code is the original root cause unless the captured CI fails at that same stage.
5. Do not change packaging metadata, dependency declarations, tox configuration, workflow matrices, or supported-runtime declarations merely to make an ad-hoc local environment run. Such changes require direct evidence from the authoritative CI failure stage.
6. Create a reversible snapshot of the last-known-good working tree before every candidate change. Rerun the original failing test and then the relevant full suite, and compare exact before/after failing node IDs and exception classes. If the pass count decreases, a new failing node appears, or a new exception class appears, restore that snapshot immediately. Never debug a regression introduced by the candidate patch on top of that same patch.
7. Keep unrelated packaging, dependency, and behavior changes out of the repair. A successful import, installation, or partial test run is not evidence that the CI build is fixed.
8. Generate deliverable patches from version-control differences rather than hand-counting unified-diff hunks. Verify each patch with `git apply --check` against a clean copy, apply it once, and confirm that the applied working tree is exactly the version that passed.
9. Treat every interpreter actually exercised by the authoritative CI/reproducer as a blocking gate. Record unavailable interpreters separately as infrastructure limitations rather than hiding them by changing the matrix or tox configuration.
10. Do not finish after announcing a next command. Finish only after the requested diagnosis note and version-control-generated patch files exist, each patch passes `git apply --check` against a clean copy, and the authoritative build command has completed successfully; otherwise document a separately verified infrastructure blocker.

### Evidence hierarchy

When evidence conflicts, use this order:

1. Captured original CI/reproducer logs from the failed job.
2. The benchmark-provided authoritative build/reproducer script run against the failed repository.
3. The repository's own configured test command under the recorded runtime/dependency conditions.
4. Narrow diagnostic commands that preserve the same environment.
5. Newly constructed local install/test environments.

Lower-ranked evidence may explain a blocker, but must not silently replace a higher-ranked failure as the repair target.

## Examples

```bash
# Analyze CI failures for a PR
uv run skills analyze-ci https://github.com/mlflow/mlflow/pull/19601

# Analyze specific job URLs directly
uv run skills analyze-ci https://github.com/mlflow/mlflow/actions/runs/12345/job/67890
```
