---
name: nlp-research-repo-package-installment
version: "1.3"
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
- First identify the exact output path requested by the task for environment provenance. Use that exact path; do not substitute a generic filename.
- Record:
  - `<selected-python> -VV`
  - `<selected-python> -m pip --version`
  - `<selected-python> -m pip freeze`
- The provenance file must describe the **same interpreter used to run the reproduction test**, not the system interpreter if a project-specific environment is required.

3. **Compare & decide — this is a blocking gate**
- If the repo declares a specific Python major/minor, the test/reproduction **MUST run under that major/minor**.
- Do not continue with dependency installation, unit tests, result generation, or final provenance logging while the selected interpreter does not match the repo declaration.
- If environment creation fails, repair the environment setup. **Never fall back to a different system Python merely because setup is inconvenient or blocked by PEP 668.**
- Prefer installing from the repo’s dependency files (avoid random upgrades), then run a quick import/smoke test.

### PEP 668 / environment-creation recovery

If `python3 -m pip install ...` fails with `externally-managed-environment`, that is an environment-setup failure, not permission to abandon the required Python version.

Use an isolated installer/environment path. For example, when `uv` is needed:

```bash
python3 -m pip install --user --break-system-packages uv
export PATH="$HOME/.local/bin:$PATH"
uv python install <required-python-version>
uv venv --python <required-python-version> /opt/repro-env
```

Then use the environment's interpreter explicitly for every subsequent command:

```bash
/opt/repro-env/bin/python -VV
/opt/repro-env/bin/python -m pip install ...
/opt/repro-env/bin/python -m <project-test-module>
```

Do not switch back to bare `python` unless `command -v python` and `python -VV` prove that it is the intended project interpreter.

## SimPO reproduction: Python 3.10 is mandatory

For the SimPO repository used by `simpo-code-reproduction`, the repository itself is authoritative:

- `environment.yml` pins `python=3.10.14` and `python_abi=3.10`.
- The repository README also instructs creating the environment with Python 3.10.

Therefore this task has a non-bypassable environment gate. Create one project Python 3.10 environment and use it consistently for installation, execution, output generation, and provenance. Do not silently fall back to the system Python after a setup failure.

**Blocking completion invariant:** before editing or running the unit test, `/root/SimPO/rich/__init__.py` must exist. Importing `rich` only from the selected virtual environment does not satisfy this invariant. An independent Python 3.10 replay uses `/root/SimPO` on `PYTHONPATH` but does not inherit that virtual environment's private `site-packages`; therefore the repository-visible copy is required in every permission branch.

1. Select the environment path according to actual write permissions. Use `/opt/py310` when `/opt` is writable; otherwise use the writable `/root/py310` path. A permission failure at `/opt` is a signal to take the documented writable branch, not to abandon Python 3.10:

```bash
if test -w /opt; then
  export PY310_ENV=/opt/py310
else
  export PY310_ENV=/root/py310
fi
uv python install 3.10.14
uv venv --python 3.10.14 "$PY310_ENV"
"$PY310_ENV/bin/python" -m ensurepip --upgrade
export PY310="$PY310_ENV/bin/python"
```

2. Use **only `$PY310 -m pip`** to install dependencies. Follow `environment.yml` / repository metadata rather than a guessed minimal subset, and include the complete imports required by the unit-test path. A successful direct run is not sufficient if an independent clean replay would fail with `ModuleNotFoundError`. For this SimPO stack, verify the full trainer import path, including `rich`:

```bash
"$PY310" -c "import torch, transformers, trl, accelerate, datasets, rich"
"$PY310" -c "from trl.trainer import CPOTrainer; from rich.console import Console, Group"
```

3. **Mandatory before the first unit-test run, regardless of whether `/opt/py310` or `/root/py310` was selected:** install `rich` and its pure-Python dependencies into the repository path. Execute this exact block even when `"$PY310" -c "import rich"` already succeeds:

```bash
"$PY310" -m pip install --no-cache-dir --upgrade --target /root/SimPO "rich==11.2.0"
test -f /root/SimPO/rich/__init__.py
PYTHONPATH=/root/SimPO "$PY310" -c \
  "import rich; from rich.console import Console, Group; from trl.trainer import CPOTrainer; assert rich.__file__.startswith('/root/SimPO/')"
```

Treat any failure in this block as an unfinished environment setup: repair it before touching `simpo_loss`. Do not edit the provided unit-test or validation files to make imports pass. Resolve dependency visibility through the environment and repository path.

4. Before running `unit_test/unit_test_1.py`, verify the exact interpreter:

```bash
"$PY310" -VV
```

The output must contain `Python 3.10`. If it does not, stop and repair the environment.

5. Run the SimPO unit test using that exact interpreter and the repository on `PYTHONPATH`. Do not run it with the default Python 3.12 interpreter:

```bash
cd /root/SimPO
PYTHONPATH=/root/SimPO "$PY310" /root/SimPO/unit_test/unit_test_1.py
```

6. Generate `/root/loss.npz` from that Python 3.10 execution.
7. The task requests `/root/python_info.txt`; write it with the same selected interpreter:

```bash
"$PY310" -VV > /root/python_info.txt
"$PY310" -m pip freeze >> /root/python_info.txt
grep -qi '^Python 3\.10' /root/python_info.txt
test -f /root/loss.npz
```

8. **Clean-replay gate before finishing:** first repeat both repository-visible checks from step 3. Then remove only the generated `/root/loss.npz`, rerun the exact command from step 5 with `$PY310`, and confirm that it recreates `/root/loss.npz` without installing anything else.

Do not finish the task if the final provenance file says Python 3.11, 3.12, or any other non-3.10 interpreter; if the selected environment is missing required imports; if `/root/SimPO/rich/__init__.py` is absent; if `rich.__file__` does not resolve under `/root/SimPO`; or if the clean replay fails, even when an earlier numerical loss appeared correct.
