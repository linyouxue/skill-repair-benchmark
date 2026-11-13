---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially
  legacy multi-module builds and Maven Invoker integration tests (and ensure required
  `failed_reasons.txt` + `patch_*.diff` artifacts are produced).
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Toolchain + failure reproduction (do this before editing)

1. Resolve the concrete checkout path under `/home/travis/build/failed` and `cd` into `/home/travis/build/failed/<repo>/<id>` (the directory that actually contains the root `pom.xml`):
   - `ls -la /home/travis/build/failed`
   - `ls -la /home/travis/build/failed/<org>` (e.g. `google`)
   - `ls -la /home/travis/build/failed/<org>/<repo>` (e.g. `auto`)
   - `ls -la /home/travis/build/failed/<org>/<repo>/<id>` then `cd /home/travis/build/failed/<org>/<repo>/<id>`
   - Confirm you’re in the build root: `pwd` and `ls -la` (should show `pom.xml`).
2. Pick the build entrypoint consistently:
   - If `./mvnw` exists, use `./mvnw` (run `chmod +x ./mvnw` if needed).
   - Otherwise use system Maven: `mvn`.
3. Create/update `/home/travis/build/failed/failed_reasons.txt` and record the toolchain and context **before** fixing anything:
   - repo path (`pwd`)
   - Maven info (`./mvnw -v` or `mvn -v`)
   - Java info (`java -version`)
4. Reproduce using a CI-like lifecycle goal: `mvn -e verify` (or `./mvnw -e verify`), then immediately add to `/home/travis/build/failed/failed_reasons.txt`:
   - the exact command used,
   - the *first* concrete failure (copy the relevant log excerpt),
   - whether it’s code vs build config,
   - your minimal fix plan.
   - Prefer passing flags on the command line while diagnosing. Do **not** “fix” builds by committing `-o` (offline mode) into `.mvn/maven.config`; it can introduce new resolution failures if artifacts are not already cached.

Only after you have the *first* concrete failure should you change code/config. Avoid broad edits (e.g., removing parents, upgrading unrelated dependencies) until you can tie them directly to that first failure.

## If Maven fails before compilation/tests: fix dependency resolution first

If the log fails during dependency resolution (no compilation has started yet), stop and repair the specific POM/dependency/plugin configuration causing that resolution error. Re-run the same `mvn -e verify` afterward to ensure you moved past the original failure.

## Java 9+ compatibility: `tools.jar` / `com.sun:tools` system dependency

If you see an error like:

```text
Could not find artifact com.sun:tools:jar:… at specified path …/lib/tools.jar
```

that’s almost always a Java 9+ incompatibility: `tools.jar` existed in JDK 8 but was removed starting Java 9, so any `<scope>system</scope>` dependency pointing at `${java.home}/../lib/tools.jar` will break on Java 11+.

Repair workflow:

1. Locate the declaration(s) by copying the coordinates/path from the Maven error and searching (avoid hand-typed guesses):
   - `rg -n "com\.sun:tools|tools\.jar" pom.xml **/pom.xml` (or `grep -RIn` if `rg` is unavailable)
2. Update the POM so Java 9+ builds do **not** try to resolve `tools.jar`:
   - Prefer removing the system-scoped `com.sun:tools` dependency when the build runs on a full JDK.
   - If Java 8 support is still needed, gate the `tools.jar` dependency behind a JDK-8-only Maven profile (e.g., activate only for `[1.8,1.9)`), so Java 11 doesn’t attempt to resolve it.
3. Re-run `mvn -e verify` to confirm dependency resolution proceeds past the original error.

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

first ask which Guava version the failing nested build actually selected.
`MoreObjects` is an API-version signal: a stale/transitively selected Guava can
make valid test source fail even though the main reactor uses a newer Guava.

For test libraries that are designed to be version-coupled (for example
`guava` and `guava-testlib`), prefer an explicit, synchronized dependency set.
Do not "fix" valid source by rewriting it to avoid the missing API unless the
source itself is demonstrated to be wrong.

## Repository-specific checkpoint: Google Auto / AutoValue

In this Google Auto snapshot, common CI breakages tend to be:

- **Early failure on Java 11+**: `com.sun:tools` / `tools.jar` system dependency in a root/module POM (fix using the Java 9+ workflow above).
- **Later Invoker failure** (only after the main build runs far enough to execute Invoker): AutoValue functional integration test rooted at:
  ```text
  value/src/it/functional/pom.xml
  ```
  If the Invoker log shows missing Guava/Truth APIs, synchronize that functional-test POM as one coherent dependency repair rather than piecemeal edits:
  - `com.google.code.findbugs:jsr305` -> `3.0.0` (`provided`);
  - `junit:junit` -> `4.12` (`test`);
  - add a direct `com.google.guava:guava:19.0` test dependency;
  - `com.google.guava:guava-testlib` -> `19.0` (`test`);
  - `com.google.truth:truth` -> `0.28` (`test`).

## Build-repair artifact contract

This benchmark requires both a diagnosis artifact and an applicable patch. Before finishing:

1. Ensure `/home/travis/build/failed/failed_reasons.txt` exists and includes: toolchain (`mvn -v`/`java -version`), the exact command used to reproduce, the first real error, and the minimal root cause + plan.
2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (or higher `{i}`) containing the intended source/configuration change (common workflow: edit files → `git diff > patch_1.diff`).
3. Apply that patch to the failed repository (e.g., `git apply patch_1.diff`). If you generated the patch from local edits, you can make the diff the source-of-truth by doing: `git reset --hard` (keeps `patch_1.diff`) → `git apply patch_1.diff`.
4. Check `git diff`/`git status`, then rerun the same Maven command and ensure the original failure is gone (ideally `BUILD SUCCESS`).

## Minimal diagnostic sequence

```bash
# Locate the checkout (example org/repo layout).
ls -la /home/travis/build/failed
ls -la /home/travis/build/failed/<org>
ls -la /home/travis/build/failed/<org>/<repo>
cd /home/travis/build/failed/<org>/<repo>/<id>

# Reproduce with a CI-like lifecycle goal (use ./mvnw if present).
mvn -e verify

# If you see a tools.jar/com.sun:tools resolution error, locate it in POMs.
rg -n "com\.sun:tools|tools\.jar" pom.xml **/pom.xml

# If Invoker reports a failing src/it POM, inspect that nested POM + build logs.
sed -n '1,220p' value/src/it/functional/pom.xml
find . -path '*target/it*' -name build.log -print
```

## General Maven lifecycle reminders

- In multi-module projects, use the reactor summary to identify the first
  genuinely failing module, then inspect that module's own integration steps.
