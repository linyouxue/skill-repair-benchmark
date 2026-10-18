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

**CRITICAL: interpreter consistency**
- After you create a new env/venv, **do not assume** `python` now points to it.
- Either **activate** the env (and keep it active) *or* use the **absolute path** to the target interpreter for **every** subsequent command (installs, logging, running unit tests).
- Immediately before generating `/root/python_info.txt`, verify you are using the intended interpreter:
  - `which python`
  - `python -VV`
  - `python -m pip --version`

If the env is located at `/opt/py310`, generate the log with the absolute interpreter to avoid PATH ambiguity:
- `/opt/py310/bin/python -VV > /root/python_info.txt`
- `/opt/py310/bin/python -m pip --version >> /root/python_info.txt`
- `/opt/py310/bin/python -m pip freeze >> /root/python_info.txt`

Note: verifiers may assert the exact logged version string (e.g., it must contain `python 3.10`). Installing Python 3.10 is insufficient unless the commands that generate artifacts actually use that interpreter.

3. **Compare & decide**
- If the repo expects a specific Python major/minor and the current Python does not match, it’s usually best to **set up a matching environment**  before installing dependencies.
        Example: set up a fresh Python 3.11 environment (Docker / Ubuntu) with uv
        # Install uv
        apt-get update
        apt-get install -y --no-install-recommends curl ca-certificates
        rm -rf /var/lib/apt/lists/*
        curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh
        export PATH="/root/.local/bin:$PATH"

        # Install Python + create a venv
        uv python install 3.11.8
        uv venv --python 3.11.8 /opt/py311

        # Use the new Python for installs/runs (prefer absolute path to avoid PATH issues)
        /opt/py311/bin/python -VV
        /opt/py311/bin/python -m pip --version
        /opt/py311/bin/python -m pip install -U pip setuptools wheel
        # From here on, run installs, logging, and tests with /opt/py311/bin/python (or keep the env activated and re-check with `which python`).

- Prefer installing from the repo’s dependency files (avoid random upgrades), then run a quick import/smoke test.


## After creating the matching environment (must-follow workflow)
1. **Select the interpreter once and reuse it everywhere**
   - Prefer absolute interpreter path (most robust):
     - `PY=/opt/py310/bin/python` (example)
     - `$PY -VV`
     - `$PY -m pip install -U pip setuptools wheel`
     - `$PY -m pip install -r requirements.txt`
     - `$PY /root/SimPO/unit_test/unit_test_1.py`

2. **Sanity check PATH/activation** (if you chose activation instead of absolute paths)
   - `which python` must point inside the env
   - `python -VV` must match the repo-required major/minor
   - `python -m pip --version` must reference the same env site-packages
