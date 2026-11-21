---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Toolchain selection (Maven wrapper vs system Maven)

1. **Prefer the project’s Maven Wrapper** if present:
   - `./mvnw -v` (or `./mvnw.cmd -v` on Windows)
2. Otherwise use system Maven:
   - `mvn -v`

Record the chosen toolchain (Maven + Java versions) in the diagnosis notes.

## Failure reproduction: command conventions

Use a two-stage reproduction so you don’t miss failures hidden behind multi-module ordering or integration-test harnesses.

### Stage A — reproduce the top-level failure

From the repository root:

```bash
# Start with a clean, verbose-enough run.
# Prefer `verify` because it includes tests and common integration steps.
./mvnw -e -DtrimStackTrace=false clean verify
# or
mvn -e -DtrimStackTrace=false clean verify
```

If the build is large, you may iterate with:

```bash
# Re-run only the failing module(s) once identified
./mvnw -e -pl :<artifactId> -am test
```

Always capture the **first concrete error** (compiler error, test failure, plugin execution failure). Do not jump to dependency edits until you have that first error.

### Stage B — if Maven Invoker is involved, reproduce the nested build

If output mentions `maven-invoker-plugin` or shows something like:

```text
The following builds failed:
*  <path>/pom.xml
```

then reproduce and debug the nested build:

1. Locate the integration-test project directory (often under `src/it/<name>`).
2. Inspect the invoker logs:

```bash
# Common locations; adjust to the repo
find . -path '*target/it*' -name build.log -o -name invoker*.log -print
```

3. Run Maven directly in the nested project directory to get a tight loop:

```bash
cd <nested-it-dir>
../mvnw -e -DtrimStackTrace=false test
# or
mvn -e -DtrimStackTrace=false test
```

This avoids guessing: you see the nested project’s **effective POM** and resolved dependency set.

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
5. Repair the nested dependency/configuration drift instead of broad-editing
   unrelated top-level modules.

Do not assume versions declared in the parent module automatically govern an
Invoker integration-test POM. An integration-test POM copied or synchronized
separately can become stale.

## Missing library classes usually indicate dependency-version drift

For a compiler error such as:

```text
cannot find symbol: class MoreObjects
location: package com.google.common.base
```

first ask which Guava version the failing build actually selected.
`MoreObjects` is an API-version signal: a stale/transitively selected Guava can
make valid test source fail even though the main reactor uses a newer Guava.

For test libraries that are designed to be version-coupled (for example
`guava` and `guava-testlib`), prefer an explicit, synchronized dependency set.
Do not "fix" valid source by rewriting it to avoid the missing API unless the
source itself is demonstrated to be wrong.

## Repository-specific notes (do not apply blindly)

Some repositories historically fail in an Invoker integration-test project (often
under `*/src/it/*`). If you see an Invoker failure, treat any “known fix” as a
**hypothesis** only:

- Confirm the failing nested POM path from the current build output.
- Confirm the first error from `build.log`.
- Confirm the resolved versions with `mvn help:effective-pom` or
  `mvn -Dverbose dependency:tree` in the failing project.

Only then make the minimal dependency/configuration change that addresses the
observed error.

## Build-repair artifact contract (paths must match the task)

This benchmark requires both a diagnosis artifact and an applicable patch.
Before finishing:

1. Write `/home/travis/build/failed/failed_reasons.txt` with:
   - the reproduced toolchain (Java + Maven/wrapper),
   - the exact failing module or nested Invoker project path,
   - the first real error message (compiler/test/plugin),
   - the root cause category (code bug vs dependency drift vs plugin/config).
2. Create at least one non-empty standard unified diff at:
   - `/home/travis/build/failed/<repo>/<id>/patch_1.diff`
   - (and `patch_2.diff`, … if needed)
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only
   the patch artifact—was changed.

## Minimal diagnostic sequence

```bash
cd /home/travis/build/failed/<repo>/<id>

# Reproduce
./mvnw -e -DtrimStackTrace=false clean verify || mvn -e -DtrimStackTrace=false clean verify

# If Invoker is implicated, inspect nested POM(s) and logs
find . -path '*target/it*' -name build.log -print
```

## General Maven lifecycle reminders

- In multi-module projects, use the reactor summary to identify the first
  genuinely failing module, then inspect that module's own integration steps.
- Prefer fixing the **smallest scope** that explains the first failure:
  nested IT POM vs module POM vs parent dependencyManagement vs plugin config.
