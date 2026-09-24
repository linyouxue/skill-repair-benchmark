---
name: nlp-research-repo-package-installment
version: "1.0"
description: Align Python version and repo-declared dependencies (requirements.txt / environment.yml) before installing packages for NLP research code reproduction.
---

# NLP Research Repo Package Installment

When reproducing an NLP research repo, **always align the environment to the repo’s declared dependencies first**. Most failures come from **Python version mismatch** or installing packages without following `requirements.txt` / `environment.yml`.

## What to do (must run before any install)

1. **Read the repo dependency files**
- Prefer `environment.yml` / `environment.yaml` (often pins **Python** + channels + non-pip deps)
- Otherwise use `requirements.txt` (pip deps)
- If both exist, treat `environment.yml` as the base, `requirements.txt` as supplemental unless README says otherwise

2. **Log the current environment (Python version is critical)**  
Write `/root/python_info.txt` containing:
- `python -VV` *(required; Python version is often the root cause)*
- `python -m pip --version`
- `python -m pip freeze`

**Important:** the `python` you use to generate `/root/python_info.txt` must be the **same interpreter** you will use to install dependencies and run the repo/tests. If you create a new interpreter/venv, either:
- activate it before logging/installing/running, **or**
- use the absolute interpreter path consistently (recommended), e.g. `/opt/py310/bin/python ...`.

3. **Compare & decide**
- If the repo expects a specific Python major/minor and the current Python does not match, it’s usually best to **set up a matching environment** before installing dependencies.

  Example: set up a fresh Python 3.11 environment (Docker / Ubuntu) with uv
  ```bash
  # Install uv
  apt-get update
  apt-get install -y --no-install-recommends curl ca-certificates
  rm -rf /var/lib/apt/lists/*
  curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh
  export PATH="/root/.local/bin:$PATH"

  # Install Python + create a venv
  uv python install 3.11.8
  uv venv --python 3.11.8 /opt/py311

  # Use the new Python for installs/runs
  /opt/py311/bin/python -VV
  /opt/py311/bin/python -m pip install -U pip setuptools wheel
  ```

- Prefer installing from the repo’s dependency files (avoid random upgrades), then run a quick import/smoke test.

## Repro checklist (to avoid common verifier failures)

- If the task/verifier requires a specific Python version string in `/root/python_info.txt` (e.g., it asserts `'python 3.10'`), ensure:
  - you are actually running Python 3.10 (`python -VV`), and
  - you log using that same interpreter.

  Example (no activation needed):
  ```bash
  PY=/opt/py310/bin/python
  $PY -VV > /root/python_info.txt
  $PY -m pip --version >> /root/python_info.txt
  $PY -m pip freeze >> /root/python_info.txt

  # Run repo code/tests with the same interpreter
  $PY -m pytest -q
  # or
  $PY path/to/script.py
  ```
