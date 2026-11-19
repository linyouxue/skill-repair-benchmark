---
name: fix-python-build
description: Diagnose and fix Python project build/test failures with a repeatable workflow. Covers packaging (pyproject/setuptools), editable installs, isolated venvs, offline/no-network constraints, and producing patch diffs.
---

# Fix Python build/test failures (repeatable workflow)

Use this skill when a Python repository “builds locally” but fails in CI, or when `pip install`, `pip install -e`, or `pytest` fails.

## Quick setup (prevents path mistakes)

Many tasks in this category require writing files to **exact absolute paths**. Start by discovering the real repo path (the prompt often uses `<repo>`/`<id>` placeholders):

```bash
ls -la /home/github/build/failed
find /home/github/build/failed -maxdepth 2 -mindepth 2 -type d
# Then set REPO_DIR to the actual path you found
```

Define these once and reuse them:

```bash
REPO_DIR=/home/github/build/failed/<repo>/<id>
NOTE_FILE=/home/github/build/failed/failed_reasons.txt
PATCH_1="$REPO_DIR/patch_1.diff"
```

Use `"$NOTE_FILE"` and `"$PATCH_1"` in commands so you don’t accidentally write artifacts in the wrong directory.

## Task-required artifacts (notes + patch diffs)

Many build-fix tasks require you to create **specific files at specific paths** (commonly a diagnosis note plus one or more `patch_{i}.diff` files). Treat these as part of the definition of done.

**Rules of thumb**:

- Create the note file **early** (once you’ve reproduced and identified root cause).
- Create/update `patch_{i}.diff` **as soon as you have a plausible fix**, even before final polish.
- Verify the artifacts exist (`test -s …`) before moving on.

**Robust patch workflow (git-backed)**:

```bash
REPO_DIR=/home/github/build/failed/<repo>/<id>
cd "$REPO_DIR"

# Make sure new files show up in diffs
git add -N path/to/new_file.py  # repeat for any newly created files

# Produce a patch against HEAD that includes staged + unstaged changes
git diff HEAD > patch_1.diff

# Sanity check: patch exists and is non-empty
test -s patch_1.diff
```

**Optional verification** (recommended when the evaluator applies patches to a clean checkout):

```bash
# WARNING: discards your working tree changes; do this only after patch_1.diff is correct.
git checkout -- .

git apply --check patch_1.diff
git apply patch_1.diff
```

## Golden workflow

1) **Reproduce in a clean environment**

- Prefer a fresh virtualenv in the repo to avoid global/user-site pollution.
- If you suspect the environment has **no network**, consider `--system-site-packages` so the venv can reuse preinstalled build tooling.

```bash
python -m venv .venv  # or: python -m venv --system-site-packages .venv
. .venv/bin/activate

python -m pip --version
python -c "import setuptools; print(setuptools.__version__)" 2>/dev/null || true
python -c "import wheel; print(wheel.__version__)" 2>/dev/null || true
```

> Avoid `pip install -U ...` in a network-restricted environment; it often burns time retrying downloads.

2) **Install + run tests in the simplest mode first**

Start by separating packaging problems from runtime/test problems.

```bash
# Packaging smoke test (avoids installing runtime deps; build deps may still be fetched under PEP 517)
python -m pip install . --no-deps

# If pytest is available in the environment
python -m pytest -q
```

3) **Only then try editable (`-e`) if needed**

```bash
python -m pip install -e . --no-deps
python -m pytest -q
```

4) **Capture the failure and locate the true root cause**

Distinguish:

- packaging/build backend errors (install step fails)
- dependency/optional-extra issues (import errors)
- runtime/test logic failures

## Common failure patterns & fixes

### A) Editable install fails (PEP 660 / `build_editable`)

Symptom (typical):

- `pip install -e .` errors with “missing build_editable hook” or similar.

Why it happens:

- Older `pip`/`setuptools` combos may not support PEP 660 for a given backend.
- If the project **only** has `pyproject.toml` metadata and no legacy `setup.py` / `setup.cfg`, pip may be unable to fall back.

Safe approaches:

- Prefer **non-editable** install in CI unless you specifically need editable.
- If the environment is pinned to older tooling, consider adding a minimal legacy `setup.py`/`setup.cfg` *or* switching to a backend that supports editable installs in that environment.

Checklist:

- Check `python -m pip --version` and `python -c "import setuptools; print(setuptools.__version__)"`.
- Inspect `pyproject.toml`:
  - `[build-system]` backend
  - PEP 621 `[project]` metadata presence

### B) Permission denied during installs (`~/.local/bin`, user site)

Symptom:

- `pip install ...` fails with `Permission denied` writing into a user-site `bin/` or system `site-packages`.

Fix:

- Use a local venv and run `python -m pip ...` inside it.
- Avoid `pip install --user` unless the task explicitly wants it.

### C) Offline/no-network environments (build isolation tries to download)

Symptom:

- `pip install .` fails while “Installing build dependencies …” or retries to reach package indexes.

Why it happens:

- PEP 517 build isolation creates an isolated build env and then installs build requirements (typically from `[build-system].requires`). In a network-restricted environment, that install step can fail even before your project code runs.
- On many `pip` versions, the *mere presence* of `pyproject.toml` is enough to trigger a PEP 517 build (even if you removed `[build-system]`). That means an offline runner can still try to download `setuptools`/`wheel`.

Fix options (pick the least invasive that works):

1) **Separate build-tool downloads from runtime deps**

```bash
python -m pip install . --no-deps
```

2) **If it’s build isolation specifically** (tries to download `setuptools`/`wheel`):

```bash
python -m pip install . --no-build-isolation --no-deps
```

This confirms whether the project can build using whatever build tooling is already available in the current environment.

3) **Make the fix durable (don’t rely on special install flags)**

If the task/evaluator runs plain `pip install ...` (no `--no-build-isolation`), you generally need to change the repo so the *default* build path works offline:

- **Preferred**: keep PEP 517 but ensure build requirements are available offline (e.g., preinstalled or provided by an internal mirror/cache). This is environment-dependent.
- **Last resort (often works in strict offline sandboxes)**: switch to legacy setuptools packaging:
  - Add minimal `setup.py` and `setup.cfg` (or `setup.py` alone) with the needed metadata.
  - **Remove or rename `pyproject.toml`** so `pip` falls back to the legacy `setup.py` build/install path.
  - If `pyproject.toml` also contained tool config (pytest/black/etc.), move it to dedicated config files (`pytest.ini`, `setup.cfg`, `tox.ini`, etc.) before removing.

4) **If missing third-party deps prevent import/tests**

- Consider making optional integrations **lazy** (import inside functions with `try/except ImportError`) or providing stdlib fallbacks where reasonable.

### D) Patch files / diffs are missing or malformed

If the task requires producing patch diffs, don’t leave it to the end.

Checklist:

- Generate diffs from git (avoids corrupt hunks):

  ```bash
  cd /home/github/build/failed/<repo>/<id>
  git add -N path/to/new_file.py  # needed for new files
  git diff HEAD > patch_1.diff
  test -s patch_1.diff
  ```

- If you must craft diffs manually, ensure:
  - correct `diff --git` headers
  - correct `---` / `+++` paths
  - correct hunk headers `@@ -a,b +c,d @@`
  - newline at EOF

## Practical debugging commands

```bash
# Show project config
ls -la
ls -la pyproject.toml setup.cfg setup.py tox.ini requirements*.txt 2>/dev/null || true

# Show pip/setuptools/wheel
python -m pip --version
python -c "import setuptools; print(setuptools.__version__)" 2>/dev/null || true
python -c "import wheel; print(wheel.__version__)" 2>/dev/null || true

# Git status + diff summary
git status --porcelain
git diff HEAD --stat

# Find where pytest is coming from
which pytest || true
python -m pytest --version 2>/dev/null || true

# Import smoke test (replace pkgname)
python -c "import pkgname; print(getattr(pkgname, '__version__', 'imported'))"
```

## Guardrails

- Prefer minimal, reversible changes.
- Avoid hard-coding environment-specific paths or secrets.
- Keep packaging metadata single-sourced (avoid conflicting `pyproject` + `setup.cfg` metadata unless you know the toolchain behavior).
