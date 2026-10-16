# NLP Research Repo Environment Alignment

## Purpose
Reproduce an NLP research repo faithfully by aligning the Python interpreter and dependencies to the repo's declared manifest before running any code, with explicit checkpoints and a stop condition when alignment cannot be achieved.

## When to Use
Any task that reproduces results from a research repo containing `environment.yml`, `environment.yaml`, `requirements.txt`, `pyproject.toml`, or `setup.py`, especially when the verifier compares numerical outputs (e.g., loss values) against a reference.

## Procedure
- Discover: list the repo root and read every dependency manifest present. Parse the pinned Python major.minor and the versions of key libs (e.g., torch, transformers, trl, numpy) directly from the manifest. Note the task-specified log/output path exactly as given; do not invent one.
- Validate: run `python -VV`, `python -m pip --version`, `python -m pip freeze` and write them together with the parsed manifest pins to the task-specified log path (fallback `/root/python_info.txt` only if the task does not specify). Compare current Python major.minor to the manifest pin.
- Act: if Python matches, install from the manifest (`conda env create -f environment.yml` or `pip install -r requirements.txt`) in a dedicated env. If it does not match, create a matching env using whatever interpreter manager is available on the system (discover: `conda`, `mamba`, `uv`, `pyenv`, `python3.X`). If the first bootstrap route fails, try one alternative discovered on the system; if all fail, STOP and report the mismatch rather than silently using the system Python.
- Verify: activate the target env, import each key pinned library, and diff installed versions against the manifest. Only proceed to run repo code when (a) Python major.minor matches, (b) key pinned deps match, and (c) a minimal import smoke test exits 0.

## Constraints / Pitfalls
- Do not hardcode Python versions, tool versions, install URLs, or env paths; derive them from the repo manifest and system discovery each run.
- Do not use `pip install --user --break-system-packages` or system-wide installs as a silent fallback; a failed bootstrap is a STOP condition, not a downgrade to the system interpreter.
- Do not claim completion before the Verify checkpoint passes; mismatched Python or unpinned numerical libs (torch, CUDA, numpy) commonly cause reference-value drift and verifier failure.
- Use the exact output path specified by the task; do not rename or abbreviate it.