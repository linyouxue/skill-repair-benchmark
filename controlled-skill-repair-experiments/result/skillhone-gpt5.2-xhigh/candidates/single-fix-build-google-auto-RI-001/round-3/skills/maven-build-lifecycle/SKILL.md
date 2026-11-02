---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, including multi-module reactors and Maven Invoker integration-test builds under src/it.
---

# Maven Build Lifecycle — CI Repair Workflow

## IMPORTANT: Output contract for SkillHone-style build-fix tasks

Some build-repair prompts *require* specific deliverables (a diagnosis note and one
or more patch diffs) in fixed filesystem locations.

When the task prompt mentions these paths, treat them as **mandatory** and keep
them up-to-date while you work:

- Diagnosis note: `/home/travis/build/failed/failed_reasons.txt`
- Patch artifacts: `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`

Practical tips:

- Create the destination directories first (for example, `mkdir -p
  /home/travis/build/failed`).
- Start the note early (even as a draft) and append the *first real error* + your
  plan as soon as you identify it.
- Create the required files **immediately** so they exist even while you’re still
  investigating (you will overwrite/fill them later):

  ```bash
  # NOTE is always outside the repo
  NOTE="/home/travis/build/failed/failed_reasons.txt"
  mkdir -p "$(dirname "$NOTE")"
  : > "$NOTE"  # ensure the file exists

  # REPO must be the *exact* path from the task prompt.
  # Do NOT leave placeholders like <repo> or <id> in the path.
  REPO="<paste the exact /home/travis/build/failed/... repo path from the prompt>"
  cd "$REPO"

  # Always write patch artifacts in the repo root, even if you’re working in a module subdir.
  REPO_ROOT="$(git rev-parse --show-toplevel)"
  PATCH1="$REPO_ROOT/patch_1.diff"
  : > "$PATCH1"  # placeholder; overwrite after edits
  ```

- Generate patch files from your final changes and confirm they are **non-empty**
  and in **unified diff** format (avoid color codes):

  ```bash
  git diff --no-color HEAD > "$PATCH1"   # staged + unstaged vs HEAD
  test -s "$PATCH1"
  ```

## 0) Pick the build toolchain (wrapper > system Maven)

- If the repo contains `./mvnw` (or `.mvn/`), prefer it to match the project’s
  expected Maven version.
- Otherwise, use the system `mvn`.
- Record tool versions in your notes:
  - `java -version`
  - `./mvnw -v` or `mvn -v`

Wrapper reliability notes (common CI/local mismatch):

- If `./mvnw` exists but fails with **permission denied**, make it executable:
  `chmod +x ./mvnw`.
- If `./mvnw` exists but fails due to **line endings** or a shell mismatch,
  invoke it explicitly: `bash ./mvnw -v` (or `sh ./mvnw -v`).
- **Do not silently fall back to system `mvn` when a wrapper is present but
  failing.** Fix the wrapper invocation first; only use system `mvn` when the
  wrapper truly does not exist.

Avoid upgrading Java/Maven unless the failure is clearly caused by an
incompatible toolchain *and* the task permits toolchain changes. For most build
repairs, the fix belongs in POMs/source, not the environment.

## 1) Reproduce the failure exactly, then minimize

1. First, try to discover the exact CI build command (preferred): check common
   files like `.github/workflows/*`, `.travis.yml`, `Jenkinsfile`, or `Makefile`.

2. If the exact CI command is unknown, start with the *narrowest* lifecycle that
   should still reproduce the problem:

   - For compilation + unit tests: `test`
   - For integration-test builds (Failsafe/Invoker): `verify`

   If unsure, run `test` first; if it passes but CI still fails, rerun with
   `verify`.

   ```bash
   # Wrapper preferred when present
   ./mvnw -B -e -V test
   # or, if there is no wrapper:
   mvn -B -e -V test
   ```

   Add `-DtrimStackTrace=false` when the root error is being suppressed.

3. In multi-module builds, use the Reactor Summary to find the *first* failing
   module; later failures are often cascading.

4. Narrow scope once reproduced:

   - `-pl <module> -am` to focus on one module while still building its
     dependencies.
   - `-DskipTests` / `-DskipITs` (if supported by the project) to separate
     compilation failures from test failures.

## 2) Maven Invoker plugin: the failure may be inside `src/it/*`

`maven-invoker-plugin` can launch independent Maven builds from integration-test
projects (commonly under `src/it/**/pom.xml`). These nested builds have their own
resolved dependency graph and can fail even when the main reactor passes.

If Maven prints output similar to:

```text
The following builds failed:
* <it-project>/pom.xml
```

then debug the nested build:

1. Locate the integration-test project directory and its `pom.xml`.
2. Read the corresponding Invoker log (often under `target/it/**/build.log`) or
   the CI output around the failure.
3. Identify the *first concrete* compiler/test error inside that nested build
   (ignore later cascade errors).
4. Compare the nested POM’s dependencies/plugins to the parent module:

   - Does it inherit from the expected parent?
   - Is it missing dependency/version alignment that the main reactor gets from
     `<dependencyManagement>`?
   - Are test-only dependencies declared with the right `<scope>`?

Do not assume versions declared in the parent automatically govern an Invoker
integration-test POM—those POMs are frequently copied and can drift.

## 3) “Cannot find symbol / ClassNotFound”: suspect dependency drift first

Compiler errors like:

```text
cannot find symbol: class MoreObjects
location: package com.google.common.base
```

usually indicate “the classpath selected an incompatible dependency version,”
not that the source is wrong.

Checklist:

- Determine the *actual* resolved version in the failing build:

  ```bash
  mvn -DskipTests dependency:tree -Dincludes=<groupId>:<artifactId>
  ```

  For Invoker tests, run dependency analysis inside the nested project (or read
  its `build.log`).

- For version-coupled libraries (for example, `guava` ↔ `guava-testlib`), keep
  versions synchronized.
- Prefer fixing POM dependency versions/scopes/exclusions over rewriting valid
  source to avoid missing APIs.

## 4) Output/patch conventions (for SkillHone-style repair tasks)

Many tasks require you to produce both a diagnosis note and patch artifacts in
fixed locations. Follow the task prompt exactly; a common contract is:

1. Write `/home/travis/build/failed/failed_reasons.txt` containing:

   - toolchain (`java -version`, `mvn -v` / `./mvnw -v`)
   - the exact command used to reproduce
   - the first real error message + file/module
   - your root-cause analysis and plan

2. Create one or more unified diffs at:

   - `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`

   Tips:

   - Prefer generating diffs from the working tree after edits:
     `git diff > patch_1.diff` (write to the **exact required path**).
   - Validate format and that the diff is non-empty (for example, `test -s
     patch_1.diff`).
   - Ensure you also apply the changes to the repository (the patch artifacts
     alone are not sufficient).

3. Apply the patch(es) to the repository and verify the project files changed
   (not just the diff artifacts).

## 5) Minimal command template (fill in the repo path)

```bash
# Set this to the *exact* repo path shown in the task prompt
# (paste the real path; do not leave placeholders like <repo>/<id>)
REPO="<paste the exact /home/travis/build/failed/... repo path from the prompt>"
cd "$REPO"

# Required note path (outside the repo)
NOTE="/home/travis/build/failed/failed_reasons.txt"
mkdir -p "$(dirname "$NOTE")"
: > "$NOTE"  # ensure the file exists early

# Patch artifacts must be written in the repo root
REPO_ROOT="$(git rev-parse --show-toplevel)"
PATCH1="$REPO_ROOT/patch_1.diff"
: > "$PATCH1"  # placeholder; overwrite after edits

# Toolchain snapshot (copy output into failed_reasons.txt)
java -version

# Prefer Maven Wrapper when present; otherwise use system mvn
if [ -f ./mvnw ]; then
  chmod +x ./mvnw 2>/dev/null || true
  MVN="./mvnw"
else
  MVN="mvn"
fi

"$MVN" -v

# Reproduce (adjust goals/profiles to match CI; start with test if unsure)
"$MVN" -B -e -V test

# If Invoker is involved, look for nested build logs
find . -path "*target/it*" -name "build.log" -print

# After making changes, rerun and write the required patch artifact(s)
"$MVN" -B -e -V test

git diff --no-color HEAD > "$PATCH1"
test -s "$PATCH1"
```
