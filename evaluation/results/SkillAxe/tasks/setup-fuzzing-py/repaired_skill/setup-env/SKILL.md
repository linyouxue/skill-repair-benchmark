---
name: setup-env
description: "When given a Python project codebase, this skill helps the agent to set up virtual environments, install dependencies, and run scripts."
---

# Skill: Use uv to manage Python environments

## Scope

1. Create a virtual environment
2. Install dependencies
3. Run Python scripts/commands

Assume `uv` is already available on PATH.

---

## Workflow selection

- If `pyproject.toml` exists: use **project workflow** (`uv sync`, `uv run`)
- Else if `requirements.txt` exists: use **pip workflow** (`uv venv`, `uv pip install -r ...`, `.venv/bin/python ...`)
- Else: stop with an error ("No pyproject.toml or requirements.txt found.")

---

## Project workflow (pyproject.toml)

### Create venv + install dependencies

From the repo root (where `pyproject.toml` is):

- `uv sync`

Notes:

- uv maintains a persistent project environment at `.venv` and installs deps there.

### Run scripts / commands (preferred)

Always run within the project environment:

- `uv run -- python <script.py> [args...]`
- `uv run -- python -m <module> [args...]`

Notes:

- `uv run` executes inside the project environment and ensures it is up-to-date.

#### Required validation step (prevents “works in .venv, fails in CI”)

After creating `.venv`, validate that the key entrypoint you generated (e.g., `fuzz.py`) can be executed using the same style as CI/verifiers:

- Prefer: `uv run --with atheris==<pinned> --with . fuzz.py -runs=3`
- If you cannot or should not install the project into the runner, use `uv run --no-project --with atheris==<pinned> fuzz.py -runs=3` **and** ensure your script adjusts `sys.path` to import the in-repo package.

Rationale: running `.venv/bin/python fuzz.py` can mask packaging/import issues that appear when `uv run` is used.

---

## Pip workflow (requirements.txt)

### Create venv

From the repo root:

- `uv venv` # creates `.venv` by default

### Install dependencies

- `uv pip install -r requirements.txt`

### Run scripts / commands

Run using the venv interpreter directly (no activation required):

- `.venv/bin/python <script.py> [args...]`
- `.venv/bin/python -m <module> [args...]`

(uv will also automatically find and use the default `.venv` in subsequent invocations when you use `uv pip ...` commands.)

---

## Minimal sanity checks (optional)

- `test -x .venv/bin/python`
- `uv pip list` (verify packages installed)
