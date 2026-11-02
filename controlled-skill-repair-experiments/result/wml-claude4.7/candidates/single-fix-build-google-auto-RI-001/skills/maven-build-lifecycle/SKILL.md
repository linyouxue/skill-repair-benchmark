---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Resolving the failed repository path

The task describes the failed checkout using a template such as
`/home/travis/build/failed/<repo>/<id>` (for example `<repo>=google` and
`<id>=auto` yields `/home/travis/build/failed/google/auto`). Before issuing any
build command:

1. Read the task description to extract the concrete `<repo>` and `<id>`.
2. Resolve `REPO_DIR=/home/travis/build/failed/<repo>/<id>` from those values.
3. Use `REPO_DIR` as the Maven working directory and as the parent directory
   for `patch_{i}.diff`. The `google/auto` paths that appear later in this
   Skill are illustrative examples of that resolution, not hardcoded invariants.

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

## Repository-specific checkpoint: AutoValue functional integration test

In this Google Auto snapshot, the historical CI failure is inside the Maven
Invoker build rooted at:

```text
value/src/it/functional/pom.xml
```

Synchronize this functional-test POM as one coherent dependency repair:

- `com.google.code.findbugs:jsr305` -> `3.0.0` (`provided`);
- `junit:junit` -> `4.12` (`test`);
- add a direct `com.google.guava:guava:19.0` test dependency;
- `com.google.guava:guava-testlib` -> `19.0` (`test`);
- `com.google.truth:truth` -> `0.28` (`test`).

## Build-repair artifact contract

This benchmark requires both a diagnosis artifact and an applicable patch.
Let `REPO_DIR=/home/travis/build/failed/<repo>/<id>` as resolved above.
Before finishing:

1. Write `/home/travis/build/failed/failed_reasons.txt` with the reproduced
   target environment, the exact failing nested POM, the first real error, and
   the dependency-drift root cause.
2. Create at least one non-empty standard unified diff at
   `${REPO_DIR}/patch_1.diff` (for example
   `/home/travis/build/failed/google/auto/patch_1.diff` when the task resolves
   to `google/auto`) containing the intended source/configuration change.
3. Apply that patch to the failed repository under `REPO_DIR`.
4. Check `git diff`/`git status` in `REPO_DIR` and ensure the intended project
   file—not only the patch artifact—was changed.

## Minimal diagnostic sequence

```bash
# 0. Resolve REPO_DIR from the task's <repo>/<id>.
#    Example only; substitute the values given by the current task.
REPO_DIR=/home/travis/build/failed/google/auto
cd "$REPO_DIR"

# 1. Reproduce the failure with the same Maven toolchain CI uses.
#    Run the reactor through the phase that triggers the Invoker integration
#    tests (for AutoValue-style projects this is typically 'verify' or
#    'install'). Capture the full log so the first real error is observable.
mvn -B -V -e -fae clean verify 2>&1 | tee /tmp/mvn-reproduce.log

# 2. Inspect the reactor summary to find the first module that actually failed
#    and the Invoker 'The following builds failed:' block, if any.
grep -nE 'BUILD FAILURE|Reactor Summary|FAIL|The following builds failed' \
    /tmp/mvn-reproduce.log

# 3. If AutoValue's Invoker functional build fails, inspect the nested POM
#    and the Invoker build log for the first concrete compiler/test error.
sed -n '1,180p' value/src/it/functional/pom.xml
find value/target/it -name build.log -print
```

Only after step 1 reproduces the failure and step 2 identifies the first
failing module/nested build should the Invoker-specific inspection in step 3
and the dependency-drift repair guidance above be applied.

## General Maven lifecycle reminders

- In multi-module projects, use the reactor summary to identify the first
  genuinely failing module, then inspect that module's own integration steps.
