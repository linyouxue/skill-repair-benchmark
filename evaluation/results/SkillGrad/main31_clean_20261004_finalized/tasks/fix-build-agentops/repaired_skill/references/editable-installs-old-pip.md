# Editable installs under older pip / restricted environments

Use this when CI/evaluator runs `pip install -e ...` and failures mention `build_editable`, PEP 660, or you see pip falling back to `python setup.py develop`.

## Procedure: reproduce, choose a strategy, and verify in the evaluator-like toolchain

1. **Capture the exact failing command** (including `-e`, paths, extras) and the toolchain versions (`pip`, `setuptools`, `wheel`, Python).
2. **Reproduce with the same toolchain** (don’t “verify” only with a newer pip).
3. **Decide which editable mechanism is in play**:
   - **PEP 660 path** (modern editable): pip asks the backend for `build_editable`.
   - **Legacy path** (fallback editable): pip runs `setup.py develop` (often writes into site-packages).
4. **Prefer PEP 660 alignment**: configure `pyproject.toml` so the evaluator toolchain can do editable installs without legacy develop.
5. If you must use **legacy develop** as a fallback, **ensure it installs to a writable target** (venv site-packages or enabled user-site) and that CI/evaluator actually uses that writable target.

```python
import os
import site
import sys


def is_writable_dir(path: str) -> bool:
    return os.path.isdir(path) and os.access(path, os.W_OK)


candidates = []
# venv site-packages often appears on sys.path
candidates.extend([p for p in sys.path if "site-packages" in p])
# user site-packages may or may not be enabled
try:
    candidates.append(site.getusersitepackages())
except Exception:
    pass

writable = [p for p in candidates if is_writable_dir(p)]
print({"python": sys.executable, "writable_site_targets": writable})
```

Decision rule: If there is **no writable install target**, do **not** rely on legacy `setup.py develop`; fix by changing the environment (create/use venv) or by avoiding editable installs.

## Runtime branch: how to act based on observed stderr

- **Branch A — stderr mentions missing `build_editable` / PEP 660**:
  1. Check `pyproject.toml` for `[build-system]` and backend.
  2. Add/adjust `build-system.requires` to include the backend’s needed build requirements.
  3. Re-run the exact editable install command under the evaluator pip.

- **Branch B — stderr mentions permission denied writing site-packages** (often after `setup.py develop`):
  1. Stop treating legacy develop as a safe fix.
  2. Reproduce inside a venv (or enable user-site, if policy allows) and verify the target is writable.
  3. If evaluator cannot use a writable target, pivot to a non-editable install strategy (sdist/wheel) or toolchain alignment so PEP 660 works.

## Verification (must prescribe next action on failure)

1. **Re-run the boundary install** (the exact `pip install -e ...` command) with the evaluator toolchain.
2. If it still fails:
   - If failure mode changed (e.g., missing hook → permission denied), **revert the change that introduced the new failure** and return to the last known failing state.
   - Then re-apply a fix that matches the current branch above (PEP 660 alignment vs writable-target enforcement).
3. After a successful install, run a minimal import smoke test (`python -c "import <pkg>"`) under the same environment to confirm the installed package is importable.

```python
import subprocess
import sys

cmd = [sys.executable, "-c", "import importlib; importlib.import_module('<package>')"]
res = subprocess.run(cmd, capture_output=True, text=True)
print({"returncode": res.returncode, "stderr": res.stderr[-400:]})
if res.returncode != 0:
    raise SystemExit("Import smoke test failed; re-check install location and packaging metadata.")
```
