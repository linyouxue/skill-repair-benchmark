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

### Output-format guardrail for list / manifest files (relative vs absolute)

When you need to write a *list file* that enumerates subprojects (e.g., `libraries.txt`) and the instruction says it must contain **relative paths**:

- Prefer **directory names** (e.g., `arrow`, `black`) or **paths relative to the stated base directory**.
- Do **not** write absolute filesystem paths (e.g., `/app/arrow`) unless the consumer explicitly requires absolute paths.

#### Must-pass stage gate (before doing any downstream work)

Immediately after writing the list/manifest file, re-open it and verify the contract **before** installing deps, generating notes, or running other steps.

Concrete self-check:

- Re-read the file you wrote and assert each non-empty line is a relative identifier:
  - must **not** start with `/`
  - must **not** contain a drive prefix / URI scheme (e.g., `C:\...`, `file://...`)
- If the list is meant to correspond to directories under a base directory (e.g., `/app`), confirm each entry resolves to an existing directory:
  - `test -d "/app/<entry>"` for each line

If the stage gate fails:

- Stop and rewrite the file to match the required representation (relative identifiers / relative paths), then re-run the checks.

(Do not “fix up” formats automatically—bind to the requirement stated in the task.)

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
