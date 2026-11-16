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

2. **Create/activate the target environment FIRST, then log environment (Python version is critical)**

**Hard requirement: interpreter consistency.** After you create the target env/venv/conda env, **every** subsequent command (installs, running scripts, unit tests, and generating `/root/python_info.txt`) must use the **same** interpreter from that environment.

Before installing or testing, record and verify the interpreter you are about to use:
- `which python`
- `python -VV`

Then write `/root/python_info.txt` using that same interpreter:
- `python -VV` *(required; Python version is often the root cause)*
- `python -m pip --version`
- `python -m pip freeze`

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



        # OPTIONAL (recommended): activate so `python` points to the target interpreter
        # source /opt/py311/bin/activate

        # Mandatory pre-flight checks (catch accidental fallback to system Python):
        which python
        python -VV
        # If not activated, use the explicit interpreter path:
        /opt/py311/bin/python -VV



        # IMPORTANT: after creating the target environment, use the SAME interpreter
        # for ALL subsequent commands (logging, installs, scripts, tests).
        # Do not switch back to the system `python` accidentally.
        # Either activate the venv or always call the interpreter explicitly.

        # Correct environment logging examples (MUST be from the target interpreter):
        # If activated:
        which python > /root/python_info.txt
        python -VV >> /root/python_info.txt
        python -m pip --version >> /root/python_info.txt
        python -m pip freeze >> /root/python_info.txt

        # If NOT activated (explicit path):
        /opt/py311/bin/python -VV > /root/python_info.txt
        /opt/py311/bin/python -m pip --version >> /root/python_info.txt
        /opt/py311/bin/python -m pip freeze >> /root/python_info.txt

        # Quick sanity check (example):
        grep -i "python 3.11" /root/python_info.txt

        # Correct execution examples:
        /opt/py311/bin/python -m pytest
        /opt/py311/bin/python -m unit_test.unit_test_1

- Prefer installing from the repo’s dependency files (avoid random upgrades), then run a quick import/smoke test.



4. **Validate the interpreter before concluding**



**Warning:** Do not run `python3 ...` / `pip ...` (system interpreter) after setup if the target is a venv/conda/uv Python. Evaluators may assert exact version substrings (e.g., `'python 3.10'`) in `/root/python_info.txt`. If you accidentally regenerate the file with system Python, the reproduction will be marked as failed even if tests pass.
- Open or grep `/root/python_info.txt` after generating it and confirm it contains the expected Python major/minor version from the target environment.
- Example checks:
  - `grep -i "python 3.10" /root/python_info.txt`
  - `head -n 5 /root/python_info.txt`
- If the file shows the wrong interpreter (for example system Python 3.12 instead of the intended 3.10 venv), regenerate the file using the correct interpreter path before running final tests or reporting completion.
