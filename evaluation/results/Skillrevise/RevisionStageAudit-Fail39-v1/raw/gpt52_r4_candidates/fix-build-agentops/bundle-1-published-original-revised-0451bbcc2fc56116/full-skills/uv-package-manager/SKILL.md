# Repo Build Repair And Patch Authoring (Git Unified Diffs)

## Purpose
Provide a repeatable workflow to reproduce a repository failure (install, build, tests), implement a minimal fix, and produce valid git-style patch_*.diff files that apply cleanly and are verified against the original failure.

## When to Use
Use this skill when you must fix a failing Python (or general) repository and deliver changes as unified diff patch files (for example patch_1.diff, patch_2.diff). Do not use for tool tutorials or migrations (uv/poetry/conda) unless the task explicitly requests changing the dependency manager.

## Procedure
- 1) Discover and restate the runnable contract (no guessing)
- Locate repo root by discovering: presence of .git, pyproject.toml, setup.cfg, setup.py, tox.ini, Makefile, or CI config.
- Identify the intended failing command(s) from task text or repo docs (README, CONTRIBUTING, CI config).
- Check tool availability (do not assume): git, python, pip, pytest/tox/nox, make. Record versions if relevant to failure (python -V, python -m pip -V).
- Checkpoint evidence: you can name (a) repo root, (b) the exact command you will run to reproduce.
- 2) Reproduce the failure in the safest reversible way
- Prefer an isolated environment for Python projects:
- Create a fresh venv in repo-local directory (name can vary; do not hard-code). Activate or use python -m pip within it.
- Run the chosen failing command exactly once to capture the first true error (do not preemptively change code).
- Save the key traceback/error lines and the command used (for later notes).
- Checkpoint evidence: terminal output shows a deterministic first failure with an error message you can point to.
- 3) If the planned route fails, take one bounded fallback branch (then return)
- If install fails (permission, editable install, backend error):
- Ensure you are in a venv (not system Python). If not, stop and create one.
- Retry with minimal environment normalization when allowed: python -m pip install --upgrade pip setuptools wheel (bounded: do this once).
- If editable install fails (pip install -e .):
- Try non-editable install (python -m pip install .) to distinguish packaging vs editable-specific issues.
- Inspect pyproject.toml [build-system] and packaging config to identify the build backend and requirements.
- Choose the smallest compatible change (for example: adjust build-system requirements, fix missing package metadata, or add a minimal backend config) rather than switching tools.
- If the same failure repeats after the fallback, stop escalating locally and switch to method-level diagnosis: open and inspect the referenced files and error locations before further retries.
- If tests fail to run due to missing test runner:
- Discover the intended runner from repo files (tox.ini/noxfile/pyproject tool config) and use that runner if present; otherwise fall back to pytest only if tests/ exists and pytest is declared.
- Checkpoint evidence: you can explain which fallback you used and show the new, smallest failing signal (changed error or confirmed same root cause).
- 4) Implement the minimal fix with tight scope
- Edit only the files necessary to address the first failure. Avoid refactors, formatting-only changes, or dependency manager migrations unless required.
- If requirements are ambiguous, add a short clarification note and implement the safest minimal change that unblocks the failing command.
- Re-run the failing command to confirm the failure is resolved or has progressed to the next actionable failure.
- Checkpoint evidence: the original failing error disappears or changes in a way that indicates forward progress.
- 5) Produce patch files safely (never hand-write diffs)
- Create patches using git-generated unified diffs only:
- Option A: git diff > patch_1.diff (for a single batch of changes)
- Option B: git format-patch (if the workflow uses commits; only if commits are allowed/available)
- Validate each patch before sharing or applying:
- git apply --check patch_1.diff
- If it fails, do not edit hunk headers manually. Instead, return to repo working tree, correct files, and re-generate the patch from git.
- If multiple patches are required, split changes into logical units by staging/committing or by generating diffs per focused change; validate each with git apply --check.
- Checkpoint evidence (execution anchor): git apply --check returns success for every patch_N.diff.
- 6) Apply and verify
- Apply patches to a clean working tree when requested (or validate application with --check if apply is not required):
- git apply patch_1.diff (then patch_2.diff, etc.)
- Re-run the original failing command after applying (and after each patch if the task expects incremental verification).
- Record final status and remaining failures (if any), and produce/update failed_reasons.txt only if the task requests it.
- Checkpoint evidence (execution anchor): (a) patches apply without errors, and (b) the failing command now passes or fails later for a new reason.

## Constraints / Pitfalls
- Do not hand-edit unified diff hunk headers, line counts, or patch context. If a patch is invalid, fix the source files and regenerate the patch via git diff or git format-patch, then re-run git apply --check.
- Do not switch dependency managers or introduce new tooling (for example uv/poetry/conda) unless explicitly required by the task. Prefer minimal, repo-native fixes and keep fallback actions bounded (one retry cycle) before escalating to deeper file-level diagnosis.