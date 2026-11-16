# Diagnose And Patch Failing Builds

## Purpose
Diagnose a failing build or test suite and produce validated unified-diff patches that make the build pass. The skill covers both local failed-build directories and remote CI job logs, selecting the branch based on inputs actually present in the environment.

## When to Use
Use when the task provides either a local repository with a failing build/test suite (and expects artifacts such as a failure summary and one or more unified-diff patches) or a PR/job URL for remote CI log analysis. Do not use for green builds, feature authoring, or tasks that do not require producing or validating diffs.

## Procedure
- Discover inputs: list the working directory and inspect any task-provided paths, PR URL, or failed-build id. If a local repo is present, branch to local-fix; if only a PR/job URL is present and the `uv run skills analyze-ci` CLI exists, branch to remote-analysis.
- Ground tooling in repo-native files: inspect `pyproject.toml`, `tox.ini`, `requirements*.txt`, `Makefile`, and `.github/workflows/*` before choosing install and test commands. Prefer the exact commands referenced there.
- Reproduce the failure: install dependencies as declared by the repo, then run the failing command (e.g., `pytest`, `make test`, or the workflow step). Capture stderr/stdout and the failing test identifiers.
- Record diagnosis: write `failed_reasons.txt` containing root cause, failing test names, key error messages, and relevant log snippets. Confirm the file is non-empty.
- Author a fix: make direct source edits in the working tree to address the root cause. Keep each logically distinct fix in its own change set.
- Generate the patch via git, not by hand: run `git diff > patch_{i}.diff` (or `git diff -- <paths>`) so hunk headers and line counts are produced correctly. Do not hand-write unified diff headers.
- Validate the patch schema: run `git apply --check patch_{i}.diff` on a clean checkout. The command must exit 0. If it fails, do not retry header edits; instead revert, re-edit sources, and regenerate with `git diff`.
- Apply and re-verify: run `git apply patch_{i}.diff` (or keep the already-edited tree) and re-run the same reproduce command. Confirm the previously failing checks now pass and no new failures were introduced.
- For remote-analysis branch only: run the provided CLI with the given URL, emit a concise failure summary, and stop (no diffs are expected).

## Constraints / Pitfalls
- Never hand-author unified diff hunk headers; always regenerate with `git diff` after editing files. If `git apply --check` fails twice on a hand-written diff, discard it and regenerate from a dirty working tree.
- Validate every `patch_{i}.diff` with `git apply --check` before claiming completion; a diff that does not pass the check is not an acceptable artifact.
- Do not assume a PR URL, `gh` auth, or the `uv run skills analyze-ci` CLI exist; verify each precondition and fall back to the local-fix workflow when they are absent.
- Do not invent install or test commands; derive them from repo-native config files. If none are found, state the gap in `failed_reasons.txt` rather than guessing.
- Bound retries: cap diff-authoring attempts (e.g., 2 per patch) before switching strategy, and cap environment-setup attempts before re-reading the repo's declared setup to avoid iteration exhaustion.
- Do not include task-instance literals (specific file paths, test names, or fix contents) as fixed steps; discover them per episode.