---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the task is to diagnose and repair a failing Python build in a broken repository under a fixed working root (e.g., `/home/github/build/failed/<repo>/<id>`), and the workflow demands a three-step deliverable: (1) a written analysis file, (2) one or more `patch_{i}.diff` files in the repo directory in standard `git`/`diffutils` diff format, and (3) actual application of those diffs so the build succeeds. Before acting, gather:
- The exact repo path and its layout (`ls`, find `pyproject.toml`, `setup.py`, `setup.cfg`, `tox.ini`, `requirements*.txt`, CI configs).
- The concrete failure signal: run the build/install/test command the project expects (e.g., `pip install -e .`, `python -m build`, `pytest`, `python -m compileall`) and capture the real error text.
- The Python version and any pinned dependency constraints referenced by the config.
- Whether errors are code-level (syntax, imports, typos, missing files) vs. configuration-level (bad metadata, wrong entry points, invalid TOML, unsatisfiable deps, missing build backend).

## Possible Failure Modes
- Writing analysis or diffs to the wrong path (e.g., outside `/home/github/build/failed/failed_reasons.txt` or not under `/home/github/build/failed/<repo>/<id>/patch_{i}.diff`).
- Producing diffs that are not valid `git apply`/`patch` input: missing `--- a/…` and `+++ b/…` headers, wrong hunk `@@` line counts, missing trailing newline, CRLF endings, or paths not relative to repo root.
- Fixing a symptom you assumed rather than the actual error printed by the build tool — skipping the step of running the build to reproduce.
- Editing files directly and forgetting to also emit the corresponding `patch_{i}.diff` (the task requires both the diff artifact and applying it).
- Applying a patch on top of already-edited files, causing "already applied" or context mismatch failures.
- Over-broad rewrites: rewriting whole files when a minimal hunk suffices, making diffs brittle.
- Ignoring configuration files (`pyproject.toml`, `setup.cfg`) when the real problem is metadata/build-backend, not source code.
- Introducing new dependencies or Python-version bumps that the environment cannot satisfy.
- Not re-running the build after applying patches, or declaring success on partial fixes.
- Touching unrelated files or leaving stray backup/temp files in the repo.

## Possible procedures
1. **Reproduce first.** `cd` into the repo and run the natural build/install command. Capture stderr verbatim. If unclear which command to use, inspect `pyproject.toml`/`setup.py`/CI files to infer it.
2. **Classify the error.** Decide: source-code bug (SyntaxError, ImportError, NameError, bad type annotation for the Python version), packaging/config bug (invalid TOML, missing `build-system.requires`, wrong `packages` entry, missing `__init__.py`, wrong version specifier), or dependency issue.
3. **Write `failed_reasons.txt`** at the exact required path with: the reproduction command, the key error lines, root-cause hypothesis, and a minimal fix plan enumerating each file to change.
4. **Draft minimal diffs.** For each file to change, produce a unified diff with:
   - Headers `--- a/<relpath>` and `+++ b/<relpath>` (relative to repo root).
   - Correct `@@ -start,len +start,len @@` hunk headers.
   - Enough context lines (typically 3) around each change.
   - LF line endings and a trailing newline.
   Save as `patch_1.diff`, `patch_2.diff`, … in the repo directory. Prefer one logical change per diff.
5. **Apply diffs** with `git apply --check patch_1.diff` first; if it fails, inspect and correct the diff rather than editing files directly. Then `git apply patch_1.diff` (or `patch -p1 < patch_1.diff` as fallback). Apply in order.
6. **Re-run the build** to confirm the failure is resolved. If a new error surfaces, iterate: append notes, create `patch_{i+1}.diff`, apply, re-verify.
7. **Decision points:**
   - If the error is a missing dependency, prefer fixing the declared dependency metadata over adding runtime workarounds.
   - If the error is Python-version syntax (e.g., walrus, f-string features, `match`), either lower the syntax or fix `python_requires`/classifiers — pick whichever preserves intent.
   - If tests fail but the task is "build," focus on making the package installable/importable; do not chase unrelated test failures unless they block the build.
8. **Recovery check:** if `git apply --check` reports "patch does not apply," re-read the target file's current bytes, regenerate the diff from the true current state, and retry.

## Verification Checklist
- [ ] `/home/github/build/failed/failed_reasons.txt` exists and contains a concrete, evidence-based analysis and plan.
- [ ] One or more `patch_{i}.diff` files exist under `/home/github/build/failed/<repo>/<id>/`, numbered sequentially starting at 1.
- [ ] Each diff is in standard unified format (`--- a/…`, `+++ b/…`, valid `@@` hunks) and passes `git apply --check` against the pre-application state.
- [ ] All diffs have been applied to the working tree (verified via `git diff` or by inspecting the changed files).
- [ ] The original failing build command now succeeds (or at minimum the specific errors identified in `failed_reasons.txt` are gone and no regressions were introduced).
- [ ] No files outside the scope of the identified root cause were modified; no stray temp/backup files remain.
- [ ] Paths in diffs are repo-root-relative, not absolute, and match the on-disk layout.
- [ ] No content, identifiers, or fixes were copied verbatim from unrelated example tasks; the changes are derived from this repository's own error output.
- [ ] If a patch failed to apply, the diff was regenerated from current file state rather than the underlying file being hand-edited to mask the mismatch.
