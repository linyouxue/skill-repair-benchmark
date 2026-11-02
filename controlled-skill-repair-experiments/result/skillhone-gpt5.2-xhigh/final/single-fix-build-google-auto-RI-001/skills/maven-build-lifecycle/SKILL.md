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
- Patch artifacts: `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff` (inside the repo directory named in the prompt)

### Do this first (creates required artifacts early)

Run this immediately after you open the repo (before deep-diving into modules), so
the required files exist even while you investigate:

```bash
# 1) Required note path (outside the repo)
NOTE="/home/travis/build/failed/failed_reasons.txt"
mkdir -p "$(dirname "$NOTE")"

# 2) Determine the repo root directory you are fixing.
# Prefer the git top-level when available; otherwise fall back to the current directory.
# (If the prompt gave you an absolute repo path, cd there first.)
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# 3) Required patch artifact path(s) live in the repo root
PATCH1="$REPO_ROOT/patch_1.diff"

# 4) Create placeholders so "note/diff exists" checks pass during investigation.
: > "$NOTE"
: > "$PATCH1"

# 5) Sanity-check paths
ls -l "$NOTE" "$PATCH1"
```

Practical tips:

- Start the note early (even as a draft) and append the *first real error* + your
  plan as soon as you identify it.
- Generate patch files from your final changes and confirm they are **non-empty**
  and in **unified diff** format (avoid color codes).

Patch generation (git repo):

```bash
git diff --no-color HEAD > "$PATCH1"   # staged + unstaged vs HEAD
test -s "$PATCH1"
```

Patch generation (no git metadata):

```bash
# BEFORE editing a file (repeat for each file you plan to change)
cp -a path/to/File.java path/to/File.java.orig

# AFTER editing
diff -u path/to/File.java.orig path/to/File.java > "$PATCH1"
test -s "$PATCH1"
```

## 0) Pick the build toolchain (wrapper when it works)

- If the repo contains `./mvnw`, try to use it to match the project’s expected
  Maven version.
- Otherwise, use the system `mvn`.
- If `./mvnw` exists but cannot run in this environment (missing execute bit, bad
  line endings, or wrapper download is blocked), **record the reason in the
  diagnosis note** and use system `mvn` as a fallback.

Record tool versions in your notes:

- `java -version`
- `./mvnw -v` or `mvn -v`

Wrapper reliability notes (common CI/local mismatch):

- If `./mvnw` exists but fails with **permission denied**, make it executable:
  `chmod +x ./mvnw`.
- If `./mvnw` exists but fails due to **line endings** or a shell mismatch,
  invoke it explicitly: `bash ./mvnw -v` (or `sh ./mvnw -v`).
- If wrapper download fails repeatedly in a restricted/offline environment, using
  system `mvn` is acceptable — but call it out in
  `/home/travis/build/failed/failed_reasons.txt` so the reviewer understands the
  toolchain choice.

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
   # or, if there is no wrapper (or it cannot run in this environment):
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
     `git diff --no-color > patch_1.diff` (write to the **exact required path**).
   - Validate format and that the diff is non-empty (for example, `test -s
     patch_1.diff`).
   - Ensure you also apply the changes to the repository (the patch artifacts
     alone are not sufficient).

3. Apply the patch(es) to the repository and verify the project files changed
   (not just the diff artifacts).

## 5) Minimal command template (fill in the repo path)

```bash
# Set this to the repo path shown in the task prompt
# (If the prompt uses placeholders like <repo>/<id>, resolve them to the real
# on-disk folder names under /home/travis/build/failed/.)
REPO="/home/travis/build/failed/<repo>/<id>"
cd "$REPO"

# Required note path (outside the repo)
NOTE="/home/travis/build/failed/failed_reasons.txt"
mkdir -p "$(dirname "$NOTE")"

# Patch artifacts must be written in the repo root
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PATCH1="$REPO_ROOT/patch_1.diff"

# Create required files early
: > "$NOTE"
: > "$PATCH1"

# Toolchain snapshot (copy output into failed_reasons.txt)
java -version

# Prefer Maven Wrapper when it works; otherwise use system mvn
if [ -f ./mvnw ]; then
  chmod +x ./mvnw 2>/dev/null || true
  if ./mvnw -v >/dev/null 2>&1; then
    MVN="./mvnw"
  else
    MVN="mvn"
  fi
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

# Prefer git-based diffs when available
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git diff --no-color HEAD > "$PATCH1"
else
  echo "Repo is not a git working tree; write a unified diff into $PATCH1 (e.g., diff -u ...)" >> "$NOTE"
fi

test -s "$PATCH1"
```
