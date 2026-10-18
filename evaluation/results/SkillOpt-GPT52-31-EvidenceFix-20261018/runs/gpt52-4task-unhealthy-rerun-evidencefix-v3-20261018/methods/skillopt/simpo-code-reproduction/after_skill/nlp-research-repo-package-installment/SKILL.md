---
name: nlp-research-repo-package-installment
version: "1.0"
description: Align Python version and repo-declared dependencies (requirements.txt / environment.yml) before installing packages for NLP research code reproduction.
---

# NLP Research Repo Package Installment

When reproducing an NLP research repo, **always align the environment to the repo’s declared dependencies first**. Most failures come from **Python version mismatch** or installing packages without following `requirements.txt` / `environment.yml`.



**Important:** Some tasks/verifiers check that `/root/python_info.txt` contains a specific Python minor version (e.g., `python 3.10`). This file must be produced by the **same interpreter** you used to install dependencies and run tests; otherwise you can pass locally but fail verification.
## What to do (must run before any install)

1. **Read the repo dependency files**
- Prefer `environment.yml` / `environment.yaml` (often pins **Python** + channels + non-pip deps)
- Otherwise use `requirements.txt` (pip deps)
- If both exist, treat `environment.yml` as the base, `requirements.txt` as supplemental unless README says otherwise

2. **Select ONE target interpreter and use it for everything (install, logging, tests)**
- Create/choose a single explicit Python executable (typically a venv) that matches the repo requirement.
- **Do not rely on bare `python`/`pip`**; they may point to system Python and fail strict verifiers.

3. **Checkpoint: confirm the interpreter you will use** *(must be done before logging or installing)*
Run using the same shell you will use later:
- `which python`
- `python -VV`
- `python -m pip --version`
If you are using a venv by path, run the equivalents:
- `/opt/py310/bin/python -VV`
- `/opt/py310/bin/python -m pip --version`

4. **Log the environment from the EXACT interpreter used for installs/tests**
Write `/root/python_info.txt` containing (using the explicit interpreter path or an activated venv):
- `<PYTHON> -VV` *(required)*
- `<PYTHON> -m pip --version`
- `<PYTHON> -m pip freeze`

Example (explicit path):
- `/opt/py310/bin/python -VV > /root/python_info.txt`
- `/opt/py310/bin/python -m pip --version >> /root/python_info.txt`
- `/opt/py310/bin/python -m pip freeze >> /root/python_info.txt`

Mandatory quick check (prevents hidden verifier failures):
- `grep -i "python 3\.10" /root/python_info.txt`

5. **Compare & decide**
- If the repo expects a specific Python major/minor and the current Python does not match, **create a matching venv and then use ONLY that venv’s interpreter for all subsequent commands** (installs, logging, tests).

Example: set up a fresh Python 3.10 environment with uv (adjust version/path as needed)

```bash
# Install uv
apt-get update
apt-get install -y --no-install-recommends curl ca-certificates
rm -rf /var/lib/apt/lists/*
curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh
export PATH="/root/.local/bin:$PATH"

# Install Python + create a venv
uv python install 3.10.19
uv venv --python 3.10.19 /opt/py310

# Always use the explicit interpreter for installs/runs
/opt/py310/bin/python -VV
/opt/py310/bin/python -m pip install -U pip setuptools wheel
```

- Prefer installing from the repo’s dependency files (avoid random upgrades), then run a quick import/smoke test using the same `<PYTHON>`.
- Reminder: If you activate the venv, still verify `which python` and `python -VV` before logging.
