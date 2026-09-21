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
Write `/root/python_info.txt` using the interpreter selected for this repository. It must contain:
- `python -VV` *(required; Python version is often the root cause)*
- `python -m pip --version`
- `python -m pip freeze`
Run these commands after activating or selecting the final environment, so the recorded interpreter and package inventory are the ones used for installation and testing.

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



## Task-specific reproduction alignment

For a task that supplies a repository, fixed test, paper, and output artifact, inspect the repository’s `environment.yml`/`requirements.txt`, README instructions, existing package layout, target implementation, and test before installing or editing. Select one compatible interpreter and use it consistently for dependency installation, implementation imports, and the supplied test; do not silently fall back to a different system `python`. Record that interpreter in `/root/python_info.txt`, install through its `-m pip` (or the repository-prescribed environment mechanism), and perform an import smoke test against the target package. Keep the provided unit test unchanged and invoke it as supplied with the same interpreter; do not substitute an ad hoc script for the required test or fabricate its expected values. If the test is intended to generate a required artifact such as `/root/loss.npz`, let that unmodified test generate it after the implementation is complete.



## Provenance and artifact validation

Before reporting success, confirm that the final `/root/python_info.txt` contains the required version and package output from the exact interpreter used for installation and test execution. Confirm that `/root/loss.npz` was produced by the unmodified repository test rather than by a replacement script, can be loaded successfully, contains the task-required `losses` key, and has the shape, dimensions, dtype/numeric finiteness, and archive schema required by that test contract. If any installation, import, test, or artifact check fails, diagnose and correct the underlying environment or implementation issue and rerun the unchanged test before claiming completion.
