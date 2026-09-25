# SKILL.md

## When to use
Use this skill when you must repair a failing **Java repository build** in a given local workspace, producing:
1) a written **analysis + plan** in a specified notes file,  
2) one or more **patch\_{i}.diff** files in standard `git diff`/GNU diff format, and  
3) the **actual applied changes** in the repo so the build succeeds.

Before acting, gather evidence by:
- Running the project’s build/test command(s) to capture the *first* and *root-cause* failures (not just downstream errors).
- Inspecting build configuration files (e.g., Gradle/Maven settings) and source code around reported line numbers.
- Confirming the required output artifacts/paths and that you can write to them.

## Possible Failure Modes
- **Skipping Step 1 artifact**: fixing code without writing a clear analysis/plan to the required notes file.
- **Misidentifying root cause**: addressing secondary compilation errors while ignoring the original missing dependency/plugin/configuration issue.
- **Patches not in standard diff format**: creating diffs that cannot be applied by `git apply`/`patch` (wrong headers, missing context, absolute paths, or non-unified diff).
- **Writing diffs to the wrong location/name**: incorrect directory, missing `patch_{i}.diff` numbering, or overwriting files unintentionally.
- **Not applying patches**: producing diff files but leaving the working tree unchanged for final evaluation.
- **Over-editing / unrelated refactors**: introducing broad formatting changes or behavior changes unrelated to the build failure, increasing risk of new failures.
- **Ignoring build tool specifics**: e.g., updating source compatibility without updating toolchain, or adjusting dependencies without refreshing lockfiles when required.
- **Not re-running the build after changes**: assuming the fix works without verification (common cause of hidden CI failures).
- **Environment mismatch**: relying on local-only state (cached artifacts, IDE configs) rather than repository-declared dependencies/settings.

## Possible procedures
1) **Locate and reproduce the failure**
   - `cd` into the repository root.
   - Run the canonical build command(s) for the repo (Gradle/Maven wrapper if present).
   - Capture: the *first failing task/phase*, the key error message(s), and referenced file/line numbers.

2) **Triage: code vs build configuration**
   - If errors indicate missing symbols/classes: check dependency declarations, module boundaries, shading/relocation rules, and source-set layout.
   - If errors indicate plugin/toolchain issues: check Java version, compiler flags, plugin versions, repository definitions, and wrapper configuration.
   - If tests fail after compilation passes: isolate failing tests; confirm whether the task expects test fixes or only compilation/build pass (use the task context as the contract).

3) **Write Step 1 notes (analysis + plan)**
   - In the required notes file, include:
     - What command failed and at which stage (compile/test/package).
     - The root-cause hypothesis with evidence (exact error excerpts).
     - A minimal, ordered plan of changes (file-level granularity).
     - Risks/alternatives if the first fix doesn’t work.

4) **Implement changes as diffs (Step 2)**
   - Make the smallest change set that plausibly fixes the root cause.
   - Prefer targeted edits:
     - Fix incorrect imports/package names, missing methods, visibility mismatches.
     - Adjust dependency coordinates/versions/scopes only as needed.
     - Align Java language level/toolchain with source usage.
   - Create one or more patch files in **unified diff** format:
     - Use `git diff` to generate each patch file.
     - Keep patches logically grouped (e.g., build config in one patch, source fix in another) if it improves reviewability.

5) **Apply patches (Step 3)**
   - Apply using `git apply` (or equivalent) and ensure the working tree reflects the edits.
   - Re-run the same build command(s) used in reproduction.
   - If new errors arise:
     - Re-triage: confirm whether the new error is a consequence of the fix or an unrelated latent issue.
     - Iterate with additional patch files, updating notes if your plan changes significantly.

6) **Recovery / iteration strategy**
   - If a change worsens the build, revert that change (or reset to a clean state) and try a narrower fix.
   - When uncertain between multiple plausible fixes, prefer the one with:
     - least surface area,
     - strongest alignment with the error message,
     - and least behavioral impact.

## Verification Checklist
- [ ] Step 1: The required notes file exists and contains (a) failure evidence, (b) root cause, and (c) an actionable plan.
- [ ] Step 2: Patch files exist at the required paths, named `patch_{i}.diff`, and are valid unified diffs (produced by `git diff` or equivalent).
- [ ] Diffs only contain changes relevant to fixing the build (no large unrelated formatting/refactors).
- [ ] Step 3: Patches have been applied to the repository (working tree shows changes consistent with the diff).
- [ ] Clean rebuild succeeds using the repo’s intended build tool (prefer wrapper scripts if present).
- [ ] If tests are part of the build pipeline, confirm test execution status matches expected “green” outcome.
- [ ] No reliance on external/manual environment state (IDE-only fixes, local caches, uncommitted files outside patch application).
- [ ] Final sanity: re-run the build from a clean state (e.g., `clean` task) to ensure reproducibility.
