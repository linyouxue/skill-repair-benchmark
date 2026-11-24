---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Maven Invoker failures: debug the nested project, not just the reactor

`maven-invoker-plugin` can launch independent Maven builds from files such as
`src/it/*/pom.xml`. Those nested builds have their own dependency mediation and
can fail even when the parent module's normal unit tests pass.

If Maven reports output similar to:

```text
The following builds failed:
*  functional/pom.xml
```

then:

1. Locate the exact integration-test POM named by the Invoker.
2. Read the corresponding Invoker `build.log` or the surrounding CI output.
3. Identify the *first concrete compiler/test error* inside that nested build.
4. Inspect the nested POM's direct dependencies and versions.
6. Repair the nested dependency/configuration drift instead of broad-editing
   unrelated top-level modules.

Do not assume versions declared in the parent module automatically govern an
Invoker integration-test POM. An integration-test POM copied or synchronized
separately can become stale.

## Toolchain selection & reproducible build invocation (convention)

When reproducing Maven CI failures in an arbitrary repository, standardize the
invocation so results are comparable and you can escalate diagnostics.

### 1) Choose Maven executable

- Prefer the Maven Wrapper if present: `./mvnw` (or `./mvnw.cmd` on Windows).
- Otherwise use system Maven: `mvn`.

Define a shell variable once:

```bash
MVN=./mvnw
[ -x ./mvnw ] || MVN=mvn
```

### 2) Record toolchain versions (for failed_reasons.txt)

```bash
$MVN -v
java -version
```

If the repo enforces a Java version via `maven-enforcer-plugin`, `toolchains.xml`,
`.java-version`, or CI config, align to that version before attempting fixes.

### 3) Default reproduction commands

- Start with the lifecycle goal that most CI jobs use:
  - `verify` (covers unit tests + integration-test/verify when configured)
  - or `test` if the project clearly only runs unit tests.

```bash
$MVN -U -e clean verify
```

Escalate only when needed:

- Add debug traces for plugin/dependency resolution issues:

```bash
$MVN -U -e -X clean verify
```

- Use `-DskipTests` / `-DskipITs` only to isolate compilation/packaging problems,
  and document why skipping is justified.

### 4) Invoker-specific reproduction

If the failure is inside an Invoker integration test, reproduce from the nested
project directory (the `.../src/it/.../pom.xml` location) or by running the
Invoker goal that triggers it, then inspect the nested build logs.

## Missing library classes usually indicate dependency-version drift

For a compiler error such as:

```text
cannot find symbol: class MoreObjects
location: package com.google.common.base
```

first ask which Guava version the failing nested build actually selected.
`MoreObjects` is an API-version signal: a stale/transitively selected Guava can
make valid test source fail even though the main reactor uses a newer Guava.

For test libraries that are designed to be version-coupled (for example
`guava` and `guava-testlib`), prefer an explicit, synchronized dependency set.
Do not "fix" valid source by rewriting it to avoid the missing API unless the
source itself is demonstrated to be wrong.

## Invoker nested-build dependency drift: generic repair procedure

When an Invoker-launched nested POM fails due to missing classes / linkage errors
/ test framework mismatches:

1. Open the failing nested `pom.xml` and identify its *direct* dependencies.
2. Determine the *effective* versions used by that nested build:

   ```bash
   # run from the nested project directory (where that pom.xml lives)
   $MVN -e -DskipTests help:effective-pom > /tmp/effective-pom.xml
   $MVN -e -DskipTests dependency:tree -Dverbose > /tmp/dependency-tree.txt
   ```

3. Look for coupled artifacts that must match (examples: `guava`/`guava-testlib`,
   JUnit + runners, Mockito + ByteBuddy, etc.).
4. Prefer fixing the nested POM (or its parent/imported BOM) so the nested build
   selects a coherent set of versions.
5. Re-run the same failing goal (`verify`/Invoker) to confirm the first error is
   gone and no new classpath conflicts were introduced.

(If you recognize a historical failure pattern from a specific repository,
keep it as an example in your notes, but do not hardcode pinned versions into
this reusable workflow.)

## Build-repair artifact contract

This task requires both a diagnosis artifact and one or more patch artifacts.
All paths must be bound to the task-provided repository root:

- Repository root: `/home/travis/build/failed/<repo>/<id>`
- Diagnosis: `/home/travis/build/failed/failed_reasons.txt`
- Patch(es): `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`

Before finishing:

1. `cd` into the task-provided repository root.
2. Write `/home/travis/build/failed/failed_reasons.txt` with:
   - toolchain (`$MVN -v`, `java -version`),
   - the exact failing module or nested Invoker POM path,
   - the first real error (compiler/test),
   - the root cause category (e.g., dependency drift, plugin config, source bug),
   - the planned minimal fix.
3. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (and `patch_2.diff` etc.
   if needed) containing the intended source/configuration change.
4. Apply the patch to the repository and verify it changed repository files:
   `git diff` / `git status` should show modifications beyond the patch file.

## Minimal diagnostic sequence

```bash
# Bind to the task-provided repository root.
REPO_ROOT=/home/travis/build/failed/<repo>/<id>
cd "$REPO_ROOT"

MVN=./mvnw
[ -x ./mvnw ] || MVN=mvn

# Record toolchain
$MVN -v
java -version

# Reproduce (adjust goal if the project clearly uses a different one)
$MVN -U -e clean verify

# If output indicates an Invoker nested build failed, locate its POM and logs.
# Examples of common locations:
#   */src/it/*/pom.xml
#   */target/it/**/build.log
find . -path '*/src/it/*/pom.xml' -o -name build.log

# Inspect the specific nested POM reported by the failure
# (replace <path-to-nested-pom> with the one from the logs)
# sed -n '1,220p' <path-to-nested-pom>

```

## General Maven lifecycle reminders

- In multi-module projects, use the reactor summary to identify the first
  genuinely failing module, then inspect that module's own integration steps.
