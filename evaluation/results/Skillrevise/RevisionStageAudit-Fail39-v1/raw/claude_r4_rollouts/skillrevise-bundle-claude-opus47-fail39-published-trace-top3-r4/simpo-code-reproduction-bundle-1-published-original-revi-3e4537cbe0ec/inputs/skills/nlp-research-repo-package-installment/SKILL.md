# NLP Research Repo Environment Alignment

## Purpose
Reproduce an NLP research repo by first aligning the Python interpreter and dependency installs to the repo's declared contract (environment.yml / requirements.txt / README), using discovery over fixed commands and verifying alignment before claiming success.

## When to Use
Any task that reproduces, trains, or evaluates code from an external research repository where mismatched Python versions or ad hoc package installs could change numerical behavior or break imports.

## Procedure
- Discover the repo contract: read environment.yml (or environment.yaml), requirements.txt, pyproject.toml, and README. Record the pinned Python major.minor, pinned package versions, and any non-pip channels. Treat environment.yml as base and requirements.txt as supplemental unless the README states otherwise. Write current `python -VV`, `python -m pip --version`, and `python -m pip freeze` to an environment log file.
- Choose isolation tool by discovery, not by literal: probe availability in order and pick the first that can create an env with the pinned Python: (a) conda/mamba if environment.yml exists and conda is on PATH, (b) uv if installed or user-installable without root, (c) python -m venv over a pyenv/system interpreter whose major.minor already matches. If none can match the pinned major.minor, stop and report the blocker; do not fall back to a mismatched system interpreter.
- Checkpoint - interpreter match: run `<chosen_python> -VV` and assert its major.minor equals the repo-pinned major.minor. If it does not match, abort before installing. Then upgrade pip/setuptools/wheel inside that env only.
- Install from the repo's declared files using `<chosen_python>` (conda env create / pip install -r / project-specific extras). Then verify: import every critical package the repo depends on, and if the repo ships a test, example, or smoke script, run it and inspect at least one concrete output (shape, finite loss, expected key). Only then declare the environment ready.

## Constraints / Pitfalls
- Do not use `--break-system-packages`, `--user`, or system Python when the repo pins a different major.minor; environment correctness outranks convenience.
- Do not hard-code Python patch versions, tool versions, or apt/curl commands; discover what the environment provides and branch accordingly. Do not skip the post-install import and smoke-run checkpoint, since silent interpreter or version drift is the dominant failure mode and will not be caught by install success alone.