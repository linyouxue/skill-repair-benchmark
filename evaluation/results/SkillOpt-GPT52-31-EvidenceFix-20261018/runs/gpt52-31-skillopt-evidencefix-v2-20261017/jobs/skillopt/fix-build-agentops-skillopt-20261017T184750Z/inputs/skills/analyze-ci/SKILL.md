---
name: analyze-ci
description: Analyze failed GitHub Action jobs for a pull request.
allowed-tools:
  - Bash(uv run skills analyze-ci:*)
---

# Analyze CI Failures

This skill analyzes logs from failed GitHub Action jobs using Claude.



## Tox / Python-matrix CI triage (tox -e pyXY)

Many Python projects run `tox` across a matrix of Python versions (e.g., `py37`, `py38`, `py39`, `py310`, `py311`, `py312`). Your goal is to quickly answer:
1) **Which tox env(s) failed?**
2) **Did they fail due to tests, or due to environment/interpreter setup?**

### 1) Read the tox summary first (identify failing envs)
In CI logs, find the tox end-of-run summary, which usually looks like:

- `py311: OK (... seconds)`
- `py312: FAIL code 1 (... seconds)`
- `evaluation failed :(`

Triage rules:
- If **only one env fails** and others pass, focus on that env’s logs.
- If **several envs fail the same way**, treat as one root cause.
- If **older envs fail instantly** while newer ones run tests, suspect missing interpreters / unsupported envs.

### 2) Classify failures: test failure vs env creation failure
**A) Test failures (code regression)**
Signals:
- `pytest`/`unittest` shows `FAILED ...` test cases and assertions.
- tox env runs commands (e.g., `pytest`, `coverage run -m pytest`) and exits non-zero.

Action:
- Extract the *first failing test* in that env and the assertion message.
- Treat this as a code issue unless evidence points to flakes/network.

**B) Environment/interpreter failures (infra/config)**
Signals (common tox patterns):
- `InterpreterNotFound: python3.7` / `python3.8` / etc.
- `could not find python interpreter` / `No Python at ...`
- Failure happens during `create`/`setup` before any tests run.
- Very short runtime for the env (e.g., `py37: FAIL (0.20 seconds)`), while others take seconds/minutes.

Action:
- Mark as **CI configuration mismatch** rather than failing tests.
- Recommend adjusting tox/CI so missing versions don’t fail the whole run.

### 3) Common remediations for missing interpreters / unsupported envs
Pick the least invasive fix consistent with the repo’s supported versions.

- **If the project no longer supports old Pythons**:
  - Remove `py37/py38/...` from tox `envlist` (or from CI matrix) and update declared support (e.g., `requires-python`).

- **If CI may not have all interpreters installed**:
  - In `tox.ini` / `pyproject.toml` tox config, consider:
    - `skip_missing_interpreters = true`
  - Or use conditional env lists / factors to only run certain envs on certain platforms.

- **If CI matrix is the source of truth**:
  - Ensure the CI installs the same versions it asks tox to run (matrix and `envlist` aligned).

### 4) Minimal local reproduction checklist (tox-centric)
Local `pytest` passing is **not sufficient** if `tox` still exits non-zero.

1) Identify failing env(s) from the tox summary.
2) Run the exact env with verbose logs:
   - `tox -e <env> -vv`
3) Confirm interpreters exist:
   - `python3.7 --version` / `python3.8 --version` etc.
   - or `pyenv versions` / `which python3.X` depending on environment
4) If env creation fails, reproduce with `tox -e <env> -vv --recreate` to confirm it’s deterministic.

### 5) Reporting (what the analysis should say)
When reporting tox/matrix failures, explicitly state:
- Failing envs (e.g., `py37/py38/py39 failed at interpreter discovery; py310/py311/py312 ran tests`).
- Whether failures are **infra/config** (missing interpreters) or **code/test** (assertion failures).
- Recommended fix (align envlist+matrix, or `skip_missing_interpreters`, or drop unsupported versions).
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



## Quick patterns to look for in tox logs

- **Missing interpreter / unsupported env**: `InterpreterNotFound`, `No such file or directory` for `python3.X`, env fails before running `pytest`.
- **Dependency/build isolation failure**: errors during `pip install` / `build wheel` / `PEP 517` steps, often repeated across envs.
- **Real test failures**: `FAILED` sections in `pytest` output; focus on the first failing assertion in the first failing env that actually runs tests.
## Examples

```bash
# Analyze CI failures for a PR
uv run skills analyze-ci https://github.com/mlflow/mlflow/pull/19601

# Analyze specific job URLs directly
uv run skills analyze-ci https://github.com/mlflow/mlflow/actions/runs/12345/job/67890
```
