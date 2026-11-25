---
name: skilltta-task-guidance
---

# SkillTTA Temporary Task Guidance: Fixing Maven/Java Build Failures

This Skill guides you through reliably reproducing Maven build failures, localizing the root cause (code vs. build configuration), planning minimal fixes, and delivering them as `git diff` patches.

## Constraints and Required Outputs

- Repository path: `/home/travis/build/failed/<repo>/<id>`
- You must create:
  - **Analysis/plan notes**: `/home/travis/build/failed/failed_reasons.txt`
  - **Patch files** (standard unified diff): `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`
- Then **apply** your patch diffs to the repo.

## Step 0 — Establish Maven Toolchain + Working Directory

1. `cd /home/travis/build/failed/<repo>/<id>`
2. Identify build tool:
   - If `pom.xml` exists → Maven.
   - If `build.gradle` exists → Gradle (but this task hints Maven lifecycle; assume Maven unless evidence says otherwise).
3. Capture baseline environment:
   - `java -version`
   - `mvn -version`

Record these in `failed_reasons.txt` if version mismatches appear relevant (e.g., code requires Java 17 but CI uses Java 8).

## Step 1 — Reproduce the Failure and Localize the Error

### 1.1 Find the correct Maven entrypoint (important with nested projects)

Many repos contain nested Maven test projects. Use:
- `find . -maxdepth 4 -name pom.xml -print`

Determine which `pom.xml` is the *reactor root*:
- Often the top-level `pom.xml` has `<modules>`.
- Nested examples/projects may be under `examples/`, `it/`, `tests/`, `integration-tests/`, etc.

**Rule of thumb**: run Maven from the root pom that CI intends. If ambiguous, test:
- `mvn -q -DskipTests help:evaluate -Dexpression=project.artifactId -DforceStdout`

### 1.2 Run the build with actionable logs

Use a deterministic sequence:
1. Clean + test:
   - `mvn -q -e test`
2. If that fails unclearly, rerun with more logs:
   - `mvn -e -DtrimStackTrace=false test`
3. If dependency resolution fails:
   - `mvn -e -U -DskipTests package`

Avoid changing multiple things before you can reproduce.

### 1.3 Classify failure type

Log the first *causal* error block and classify into one of:

**A) Compilation errors (Java code):**
- `cannot find symbol`, `incompatible types`, missing imports, method signature mismatch.
- Fix in `src/main/java` or `src/test/java`.

**B) Test failures:**
- Assertion failures or runtime exceptions.
- Decide whether tests are wrong, flaky, or environment-dependent.

**C) Maven configuration / plugin issues:**
- `Source option X is no longer supported` (compiler plugin Java version mismatch)
- `NoSuchMethodError` / `ClassNotFoundException` during tests (dependency conflicts)
- `Plugin execution not covered by lifecycle configuration`
- Surefire/Failsafe issues.

**D) Dependency resolution:**
- `Could not resolve dependencies` / missing artifact.
- Often caused by incorrect repository definitions, wrong coordinates, missing `<version>`, or relying on unavailable snapshot repos.

Record in `failed_reasons.txt`:
- The command you ran
- The module (if multi-module)
- The *first* root error lines
- Your hypothesis about the fix

## Step 1 Notes File: `failed_reasons.txt` Template

Use a structured note so Step 2 is mechanical:

- Repo path:
- Java/Maven version:
- Root build command used:
- Failure category (A/B/C/D):
- Failing module:
- Key log excerpt (10–30 lines):
- Suspected root cause:
- Proposed minimal fix:
- Files to change:
- Verification command to rerun:

## Step 2 — Plan Minimal Fixes (Prefer Small, Local, Deterministic)

### 2.1 Scope control in nested Maven projects

If there are nested test projects:
- Prefer fixing the root reactor `pom.xml` unless the failing module is clearly isolated.
- Avoid editing example/demo poms unless the build actually includes them as modules.
- If a nested project should *not* be built in CI, consider:
  - Removing it from `<modules>` (only if clearly accidental)
  - Marking it with `<skipTests>` or profiles (only if CI indicates that intent)

### 2.2 Common Maven fixes

**Compiler level mismatch**
- Add/adjust:
  - `maven-compiler-plugin` with `<source>`/`<target>` (or `<release>`)
  - Ensure it matches CI Java level.

**Surefire/Failsafe issues**
- Pin plugin versions to stable releases.
- For JUnit 5, ensure Surefire supports it and dependencies include `junit-jupiter-engine`.

**Dependency conflicts**
- Use `mvn -q dependency:tree -Dincludes=group:artifact` to locate.
- Add exclusions or align versions via `<dependencyManagement>`.

**Missing artifact / repo**
- Prefer switching to a released version available on Maven Central.
- Avoid adding unreliable external repositories unless necessary.

### 2.3 Treat fixes like “safe file ops”

Apply these defensive patterns (adapted from general robust task patterns):
- Verify assumptions before changing (e.g., confirm module is in reactor, confirm dependency exists).
- Keep changes minimal and reversible.
- Clean up after experiments (don’t leave generated files or local-only config).

## Step 2 — Write Patch Diffs

Create patch files named exactly:
- `/home/travis/build/failed/<repo>/<id>/patch_1.diff`
- `/home/travis/build/failed/<repo>/<id>/patch_2.diff`

Patch rules:
- Standard unified diff format (`diff --git ...` headers)
- One conceptual fix per patch file if possible.
- Do not include unrelated formatting/whitespace churn.

## Step 3 — Apply Patches + Verify

1. Apply patches:
   - `git apply patch_1.diff` (repeat)
2. Run the same verification command you listed in `failed_reasons.txt`:
   - Typically: `mvn -e test` or `mvn -e -DskipTests package`
3. If multi-module, confirm reactor completes and tests pass.

## Practical Checklist

- [ ] Identified correct root `pom.xml` (reactor vs nested project)
- [ ] Reproduced failure with `mvn -e ...`
- [ ] Captured root error excerpt in `failed_reasons.txt`
- [ ] Minimal fix chosen (code vs pom vs plugin)
- [ ] Patch diff created with correct paths
- [ ] Applied patch and reran Maven successfully
