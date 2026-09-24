---
name: analyze-ci
description: Analyze failed GitHub Action jobs for a pull request, and — when the task is to repair a failing build — bind completion to the verifier's exit status rather than to the first fixed error.
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

### Repair-mode completion criterion

When the task is not just to *analyze* logs but to *repair* a failing build
(cues: instruction contains verbs like "fix", "repair", "make the build pass",
or asks you to author `patch_*.diff` files and apply them), treat completion as
gated by the verifier's own signal, not by "the first error I saw is gone":

1. **Identify the success predicate up front.** Locate the exact command the
   CI / verifier runs (e.g. `tox`, `pytest`, `make test`, the workflow step in
   `.github/workflows/*.yml`). Record it before editing anything.
2. **Reproduce it locally with the same invocation.** Do not substitute a
   narrower command (e.g. running a single test file) as the completion check;
   a narrower command may hide environment or configuration deltas.
3. **Apply → re-run → observe exit status.** After each candidate patch, re-run
   the recorded command and read its exit code. Only an exit code of 0 (or the
   verifier's documented success signal) counts as done.
4. **Do not declare completion on partial green.** "Collection now works" or
   "the import error is gone" is progress, not completion, if any test the
   verifier gates on is still failing.
5. **If the verifier cannot be run locally**, state that explicitly in your
   notes and re-run the closest available proxy (same test command, same
   interpreter version) before finishing.

### Scope classification of residual failures

Under a repair task with a binary pass/fail verifier, adopt an
**in-scope-by-default** rule for every failure surfaced by the verifier's
command. A residual failure may only be downgraded to "pre-existing" or
"unrelated" when at least one of the following is documented:

- (a) the same test fails identically on the last known-good commit
  (check with `git log` / `git blame` / a checkout of the reference revision),
- (b) the task instruction explicitly excludes that test or file, or
- (c) the verifier is known not to gate on that test (e.g. it is marked
  `xfail`, skipped by config, or excluded by the CI selector).

Absent (a), (b), or (c), continue root-causing: inspect the referenced symbol
(e.g. missing attribute, unmocked URL), diff against the reference passing
state, and extend the patch. Symptoms such as `NoMockAddress`, `AttributeError`
on an internal object, or timestamp/equality assertions are frequently caused
by the same underlying regression that produced the first observed error and
should not be dismissed on intuition alone.

### Fallback when no repair is possible

If, after root-causing, a residual failure is genuinely outside the repo under
repair (e.g. upstream package bug reproducible on the reference commit),
record the evidence for (a)/(b)/(c) in your analysis notes and state clearly
that the verifier will still report failure. Do not silently finish.

## Examples

```bash
# Analyze CI failures for a PR
uv run skills analyze-ci https://github.com/mlflow/mlflow/pull/19601

# Analyze specific job URLs directly
uv run skills analyze-ci https://github.com/mlflow/mlflow/actions/runs/12345/job/67890
```
