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
Write `/root/python_int.txt` containing:
- `python -VV` *(required; Python version is often the root cause)*
- `python -m pip --version`
- `python -m pip freeze`

> **Interpreter lockstep rule (prevents “wrong Python in logs”)**
>
> In sandboxes with multiple Pythons (system Python + uv/venv/conda), **never assume `python` on PATH is the interpreter you’ll actually use**.
> Before you log provenance files (and before installs/tests), **bind to one interpreter identity and use it everywhere**:
>
> - Prefer an **absolute interpreter path** for all three phases: installs, running tests/scripts, and writing environment info.
>   Example pattern:
>   - `PY=/opt/py310/bin/python` (or your venv’s `.../bin/python`)
>   - `$PY -VV > /root/python_info.txt`
>   - `$PY -m pip freeze >> /root/python_info.txt`
>   - `$PY -m pytest ...` (or `$PY path/to/script.py`)
>
> - If you rely on PATH/activation instead, **verify the binding** right before logging:
>   - `which python` and `python -VV` should match the intended pinned version.
>
> **Artifact contract note:** if the task specifies an exact output path/name (e.g., `/root/python_info.txt`) or required substrings (e.g., it must mention `python 3.10`), follow the task contract even if this skill uses a different default filename.
>
> **Verification/fallback:** after writing the file, confirm it matches the intended interpreter:
> - `head -n 1 /root/python_info.txt` should show the expected major/minor.
> - If it doesn’t, rewrite the file using the correct interpreter’s absolute path.

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

        # Use the new Python for installs/runs
        /opt/py311/bin/python -VV
        /opt/py311/bin/python -m pip install -U pip setuptools wheel

- Prefer installing from the repo’s dependency files (avoid random upgrades), then run a quick import/smoke test.
