# SKILL.md

## When to use
Use this skill when you must repair a **failing Python repository build** under a fixed workspace path and follow a **three-phase workflow**:

1. **Diagnose** the build failure by inspecting the repo and reproducing/observing errors.
2. **Write an analysis + fix plan** to a specified notes file (used as your source-of-truth for the next phase).
3. **Propose changes as git-style diff patches** (`patch_{i}.diff`), then **apply those patches** to make the build pass.

Before editing code, gather concrete evidence:
- What command/build step fails (tests, import, lint, packaging, dependency install, type check, etc.).
- The exact error messages and stack traces.
- Whether the fault is in **project code** vs **build configuration** (e.g., packaging metadata, dependency pins, CI scripts, tool config).
- Minimal reproduction steps you can re-run after each patch.

## Possible Failure Modes
- **Skipping Step 1 notes** or writing vague notes: not capturing the *specific failing command*, *root cause*, and *intended patch list* in the required notes file.
- **Fixing symptoms instead of root cause**: e.g., adding broad try/except or disabling checks rather than resolving the underlying import, dependency, path, or configuration issue.
- **Patches not in standard diff format**: missing `---/+++` headers, incorrect file paths, or non-unified diff output that `git apply`/`patch` can’t parse.
- **Editing files directly without first producing diff files**, or producing diffs that don’t match the applied repository state.
- **Breaking unrelated behavior** while addressing the build (unnecessary refactors, formatting churn, renaming public APIs) leading to new test failures.
- **Environment/path assumptions**: hardcoding absolute paths, assuming directories exist, or relying on local machine state. (Transferable lesson from file-ops tasks: always check existence and create required directories defensively when appropriate.)
- **Ignoring validation edges**: failing to validate inputs/config types or formats where the build error originates from schema/format mismatches. (Transferable lesson: validate early with clear errors rather than letting cryptic downstream failures occur.)
- **Not re-running the failing step after applying patches**, leaving the build still broken or introducing regressions.

## Possible procedures
1. **Repository triage**
   - List top-level files to infer build system: `pyproject.toml`, `setup.cfg`, `setup.py`, `requirements*.txt`, `tox.ini`, `noxfile.py`, CI configs.
   - Search for recent/obvious breakpoints: missing modules, renamed packages, version constraints, entry points, misconfigured tool sections.
   - Run the most likely build/test command(s) locally (or the project’s documented command). Capture full stderr/stdout.

2. **Root-cause analysis (write notes)**
   - In the required notes file, record:
     - The command(s) run and which one fails first.
     - Exact error text (key lines) and where it originates (file/module/config section).
     - Hypothesis of cause and why (e.g., import path mismatch, dependency not declared, wrong optional extra, incompatible API usage).
     - A *patch plan* as a short ordered list (Patch 1: config fix; Patch 2: code change; Patch 3: test update), minimizing scope.

3. **Design minimal, targeted fixes**
   - Prefer the smallest change that restores the expected behavior:
     - If dependency-related: add/adjust dependency declarations; avoid over-broad version pins unless necessary.
     - If import/package layout: fix module paths, `__init__.py`, package discovery, or relative imports.
     - If configuration: correct tool configuration keys/sections; ensure consistent naming across config and code.
   - Apply defensive practices where relevant (inspired by common robust patterns):
     - Check file/dir existence before operations.
     - Use clear, specific exceptions and messages for invalid states.
     - Avoid side effects at import time that break test/build discovery.

4. **Create patch diffs (before applying)**
   - For each logical change set, create a separate `patch_{i}.diff`.
   - Ensure unified diff format with correct paths and context lines.
   - Keep patches coherent: don’t mix formatting-only changes with functional fixes unless required.

5. **Apply patches and iterate**
   - Apply patches using a standard tool (`git apply` or `patch`) and resolve any offsets/rejections by regenerating diffs against the current tree.
   - Re-run the originally failing command(s) after each patch to confirm progress.
   - If the first failure is fixed but a later step fails, update notes (briefly) and add an additional patch diff with the next fix.

6. **Recovery checks**
   - If evidence is ambiguous, add lightweight instrumentation (temporary logging) only if necessary, and remove it before finalizing.
   - If you suspect configuration mismatch, validate the config against tool documentation or by running the tool in verbose mode.

## Verification Checklist
- [ ] The required analysis/plan file exists at the specified path and includes: failing command, key error lines, root-cause explanation, and an ordered patch plan.
- [ ] One or more `patch_{i}.diff` files exist under the repo path, each in valid unified diff format (`---`, `+++`, `@@` hunks) and with correct relative file paths.
- [ ] Patches are **minimal and scoped**, avoiding unrelated refactors and preserving unrelated repository state.
- [ ] All patches apply cleanly to the current repo state (no rejects).
- [ ] The original failing build/test/install step is re-run and now succeeds; any secondary failures are also resolved or explicitly accounted for.
- [ ] No new failures are introduced in common checks (imports, unit tests, packaging/build step).
- [ ] The final modifications are derived from the target repo’s evidence; nothing is copied as “facts” from retrieved examples (only general tactics/patterns are reused).
