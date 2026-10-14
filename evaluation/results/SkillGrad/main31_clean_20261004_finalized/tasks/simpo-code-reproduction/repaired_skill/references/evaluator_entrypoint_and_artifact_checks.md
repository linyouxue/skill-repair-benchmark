# Evaluator entrypoint alignment & artifact verification

Use this when the evaluator runs a specific command (often a unit test) and your manual runs don’t match it, or when the task is graded by a saved artifact on disk (e.g., `/root/loss.npz`).

## Goal

1) Make the repo importable **exactly** as the evaluator entrypoint imports it (no fragile one-off hacks), and 2) treat “artifact was produced” as a claim that must be verified by loading and inspecting the file.

## Checklist (do in order)

### 1) Identify and run the evaluator command from the right working directory

Typical evaluator entrypoints:
- `python -m pytest ...`
- `python path/to/unit_test.py`
- `python -m package.module`

Run it from the repo root unless the entrypoint explicitly documents another working directory.

```bash
pwd
ls
python -VV
python -c "import sys; print('cwd', __import__('os').getcwd()); print('path0', sys.path[0])"
```

Runtime branch:
- If the evaluator runs a file path like `python unit_test/unit_test_1.py`: `sys.path[0]` becomes `unit_test/`, so imports like `import scripts` may fail unless the repo is installed or the repo root is on `PYTHONPATH`.
- If the evaluator runs a module like `python -m unit_test.unit_test_1`: imports usually resolve from the repo root (better).

### 2) Make imports resolve without editing tests

Prefer one of these stable strategies:

**Strategy A — editable install (best when repo has packaging metadata):**
```bash
python -m pip install -e .
python -c "import importlib; importlib.import_module('scripts'); print('ok')"
```

**Strategy B — run with repo root on `PYTHONPATH` (when packaging is absent):**
```bash
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
python -c "import importlib; importlib.import_module('scripts'); print('ok')"
```

Runtime branch:
- If `pip install -e .` fails because there is no `pyproject.toml/setup.py`: use Strategy B.
- If Strategy B fixes imports, consider adding a minimal packaging wrapper only if allowed by the task; otherwise keep the environment variable approach consistent across runs.

### 3) Freeze dependency drift before chasing runtime errors

Before upgrading anything, check the repo’s pinned versions and align to them. If you must change a version, record it and be prepared to undo it.

```bash
python -m pip --version
python -m pip freeze | sed -n '1,80p'
```

Runtime branch:
- If you see API errors after upgrading (missing symbols/classes): revert to repo-pinned versions.
- If you see ABI errors (e.g., `pyarrow`/`numpy` mismatch): bring the compiled deps into a mutually compatible set by pinning (often easiest in a fresh env).

### 4) Artifact verification (must be done immediately after the run)

If the evaluator expects a file on disk, verify it in three layers: existence → schema → spot-check values.

```python
from pathlib import Path
import numpy as np

p = Path("/root/loss.npz")  # replace when the task specifies a different path
assert p.exists(), f"missing artifact: {p}"

obj = np.load(p)
print("keys:", list(obj.files))

# If you expect a single array, load it; otherwise iterate.
arr = obj[obj.files[0]]
print("shape:", arr.shape, "dtype:", arr.dtype)
print("sample:", arr.reshape(-1)[:5])

# Optional: catch NaNs/Infs early.
assert np.isfinite(arr).all(), "artifact contains NaN/Inf"
```

## Verification and corrective action

**Verification:**
- The evaluator entrypoint runs far enough to reach the code you’re modifying.
- The artifact file exists at the exact expected path.
- The artifact loads and contains expected keys and plausible shapes/dtypes.

**If verification fails:**
1. If imports fail: return to step (2) and choose Strategy A vs B; confirm `python -c "import scripts"` succeeds *before* rerunning the evaluator.
2. If artifact is missing: search for the write path in code (`rglob` for the filename), confirm the working directory assumptions, and rerun the entrypoint with a clean environment.
3. If artifact schema/values are wrong: only then move on to math/semantics debugging (use the semantics references from L2) and re-run the entrypoint + artifact check each iteration.
