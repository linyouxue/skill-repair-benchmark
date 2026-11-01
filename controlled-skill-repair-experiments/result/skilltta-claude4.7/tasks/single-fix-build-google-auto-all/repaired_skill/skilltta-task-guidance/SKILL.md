---
name: skilltta-task-guidance
---

# Maven Build Failure Repair Guidance

## Scope
Fix build errors in a Java/Maven repository at `/home/travis/build/failed/<repo>/<id>`. Produce analysis notes, diff patches, and apply them.

## Workflow

### Step 1 — Analyze
1. `ls` the repo root and locate `pom.xml` (root + any nested modules, including nested test projects referenced by integration tests).
2. Inspect `.travis.yml` / `travis_build.log` (if present) and root `pom.xml` for:
   - `<modules>` list (identify nested/sub-projects, including test fixtures).
   - Declared Maven/JDK toolchain (`maven.compiler.source/target`, `java.version`, enforcer rules).
   - Plugin versions pinned to EOL artifacts.
3. Reproduce the failure deterministically before editing:
   - `cd` to the repo id directory.
   - Run `mvn -B -ntp -fae -e clean verify` (or the goal used in CI). Capture first ERROR stack and the module path.
   - If a nested test project fails on its own lifecycle, re-run inside that submodule to isolate.
4. Classify the root cause:
   - **Code**: compile errors, missing import, API drift, generics, annotation processor (e.g., AutoValue/AutoService) output mismatch.
   - **Config**: missing/incorrect dependency `<version>`, wrong `<scope>` (e.g., `provided` for annotation processors should move to `annotationProcessorPaths`), plugin version, repository URL, Java release level, module not listed in parent `<modules>`.
5. Write findings to `/home/travis/build/failed/failed_reasons.txt` with:
   - Failing module path, failing goal, exact error excerpt.
   - Root cause classification + proposed fix list (file → change).

### Step 2 — Propose Patches
- For each file to modify, create `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff` in unified `git diff` format:
  ```
  diff --git a/path/File.java b/path/File.java
  --- a/path/File.java
  +++ b/path/File.java
  @@ -L,N +L,N @@
  - old
  + new
  ```
- Keep each patch focused (one concern per diff). Prefer minimal changes.
- For nested test projects: patch the nested `pom.xml` AND, if the parent aggregates them, keep parent `<modules>` and dependencyManagement consistent.
- For annotation-processor libraries (e.g., Google AutoValue, AutoService, Dagger): ensure both the API jar and processor jar are on the right path. Prefer:
  ```xml
  <plugin>
    <artifactId>maven-compiler-plugin</artifactId>
    <configuration>
      <annotationProcessorPaths>
        <path><groupId>…</groupId><artifactId>…</artifactId><version>…</version></path>
      </annotationProcessorPaths>
    </configuration>
  </plugin>
  ```

### Step 3 — Apply & Verify
1. Apply patches: `cd /home/travis/build/failed/<repo>/<id> && git apply --whitespace=nowarn patch_1.diff patch_2.diff …` (or `patch -p1 < patch_i.diff` if not a git repo).
2. Re-run the same Maven command used to reproduce. Iterate until BUILD SUCCESS.
3. Also build any nested test module explicitly to confirm no regression: `mvn -pl <nested> -am -B verify`.

## Patterns Borrowed From Examples
- **Iterate-match-act** (like the file-move examples): walk candidate files (`pom.xml`, failing `.java`), apply a regex/criterion (error signature), act (patch). Count/track fixes applied, mirroring the `moved_files_count` discipline — every change must be justified by a matched error.
- **Download-and-scan** pattern: treat the build log as the "downloaded text", `grep -nE '\b(ERROR|BUILD FAILURE|cannot find symbol|package .* does not exist)\b'` to enumerate occurrences before fixing.
- **Archive-processed** pattern: once a file is patched, mark it (suffix in notes `_processed`) so repeated passes do not re-edit it.

## Guardrails
- Do not invent dependency versions; use versions already present in the repo's `dependencyManagement` or sibling modules.
- Do not reformat unrelated code.
- Do not add new modules unless an existing `<module>` entry references a missing directory.
- Never claim knowledge of a hidden reference fix; derive every change from observed errors + repo contents.
