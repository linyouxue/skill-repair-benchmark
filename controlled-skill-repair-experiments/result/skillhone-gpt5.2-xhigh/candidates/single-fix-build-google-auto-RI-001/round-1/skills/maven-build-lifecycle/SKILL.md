---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, including multi-module reactors and Maven Invoker integration-test builds under src/it.
---

# Maven Build Lifecycle — CI Repair Workflow

## 0) Pick the build toolchain (wrapper > system Maven)

- If the repo contains `./mvnw` (or `.mvn/`), prefer it to match the project’s
  expected Maven version.
- Otherwise, use the system `mvn`.
- Record tool versions in your notes:
  - `java -version`
  - `./mvnw -v` or `mvn -v`

Avoid upgrading Java/Maven unless the failure is clearly caused by an
incompatible toolchain *and* the task permits toolchain changes. For most build
repairs, the fix belongs in POMs/source, not the environment.

## 1) Reproduce the failure exactly, then minimize

1. Run the same goal/phase CI runs (often `test` or `verify`). If the exact CI
   command is unknown, start with `verify`:

   ```bash
   ./mvnw -B -e -V verify
   # or, if there is no wrapper:
   mvn -B -e -V verify
   ```

   Add `-DtrimStackTrace=false` when the root error is being suppressed.

2. In multi-module builds, use the Reactor Summary to find the *first* failing
   module; later failures are often cascading.

3. Narrow scope once reproduced:

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

   - toolchain (`java -version`, `mvn -v`)
   - the exact command used to reproduce
   - the first real error message + file/module
   - your root-cause analysis and plan

2. Create one or more unified diffs at:

   - `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`

3. Apply the patch(es) to the repository and verify the project files changed
   (not just the diff artifacts).

## 5) Minimal command template (fill in the repo path)

```bash
REPO="/home/travis/build/failed/<repo>/<id>"
cd "$REPO"

# Toolchain snapshot (include in failed_reasons.txt)
java -version
./mvnw -v || mvn -v

# Reproduce (adjust goals/profiles to match CI)
./mvnw -B -e -V verify || mvn -B -e -V verify

# If Invoker is involved, look for nested build logs
find . -path "*target/it*" -name "build.log" -print
```
