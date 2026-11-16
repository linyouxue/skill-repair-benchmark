# Python Project Environment + Run Loop (uv-first with fallback)

## Purpose
Set up or reuse a project-local Python environment, install dependencies using the repo's actual packaging metadata, run a requested command/script inside that environment, and verify results with a small, repeatable execute-and-recover loop.

## When to Use
Use when a task requires running Python code from a repo and dependencies may be missing or need to change (new tools, extras, test/fuzz deps, editable install), or when the environment must be isolated per project. Do not use if the task explicitly says not to modify the environment, or if an existing environment has already been proven by a successful in-env run of the same command with no dependency changes needed.

## Procedure
- 1) Discover and validate inputs (no changes yet)
- Identify the intended project root (the directory containing packaging files or the script/module to run).
- Detect packaging metadata by listing repo-root candidates: pyproject.toml, requirements.txt, setup.cfg, setup.py.
- Preflight tools:
- Check for uv availability (for example, `uv --version` or `command -v uv`).
- Check Python availability (`python --version`).
- Decision point: choose runner
- If uv is present, prefer uv-based setup/run.
- Else plan fallback: python -m venv + pip.
- 2) Create or confirm a project-local environment (must be verifiable)
- Define the environment location as a project-local directory (default: `.venv` under the project root). Do not assume it exists.
- If using uv:
- Attempt to create/sync the environment in a way supported by the repo (start with the least invasive option for the detected packaging style).
- If using venv fallback:
- Create venv at the chosen location (python -m venv <envdir>).
- Ensure the interpreter exists and is executable inside the envdir.
- Checkpoint evidence: an environment Python executable exists and runs:
- Run a trivial command using the environment interpreter/runner and confirm exit code 0 (for example: print sys.executable).
- 3) Install dependencies using discovered packaging style (plus optional extra deps)
- Decision point: install strategy (try in this order, stopping after the first success)
- If pyproject.toml exists:
- With uv: try syncing project dependencies (uv sync or the repo's documented uv workflow).
- If that fails, fall back to an editable install inside the env (pip install -e .) as the bounded alternative.
- Else if requirements.txt exists:
- Install from requirements (pip install -r requirements.txt) using the chosen environment runner.
- Else if setup.py/setup.cfg exists:
- Prefer an editable install (pip install -e .) using the chosen environment runner.
- Else: stop and ask for clarification (no supported dependency source found).
- Optional: if the task requires additional tooling deps (for example, test runners, linters, fuzzing tools), install them explicitly after base deps are installed, using the same environment runner.
- Checkpoint evidence: re-run the smoke import that the task depends on (or a minimal import like `python -c "import pkgutil"`), and confirm exit code 0.
- 4) Execute the target command/script inside the environment and capture evidence
- Run using the environment runner:
- If using uv: use `uv run -- <command...>` so execution occurs inside the managed environment.
- If using venv: invoke the environment python directly (env python -m module or env python script.py).
- Always capture stdout/stderr to a log file in the working directory (for example, `run.log`) and also capture the process exit code.
- Checkpoint evidence:
- `run.log` exists, is readable, and is non-empty.
- Exit code observed and recorded; if success is expected, exit code must be 0.
- 5) Bounded recovery if setup or execution fails (one loop only)
- If a tool is missing (uv not found) or a uv command fails:
- Switch to the venv + pip fallback and redo only the smallest necessary check (environment python exists, then re-run the target command).
- If dependency installation fails:
- Inspect the error for the narrow cause (missing build backend, extras not found, heavy optional deps).
- Apply one nearest alternative install strategy (sync -> editable -> requirements) and re-run the smoke check once.
- If execution fails:
- Use the log to classify: import error, missing file/path, runtime exception.
- Make only minimal corrective changes consistent with the task (for example, install a missing dependency explicitly), then re-run once.
- If still failing after one recovery attempt: stop and report the observed errors and what was tried.

## Constraints / Pitfalls
- Do not assume uv exists, that `.venv` is automatically created, or that pyproject.toml implies a single correct install command; always verify tool availability and environment interpreter existence before running irreversible installs.
- Avoid hard-coded paths, versions, and repo-specific commands unless discovered in the repo (README, scripts, Makefile) or required by the task; prefer discovery and verifiable checkpoints over fixed recipes.