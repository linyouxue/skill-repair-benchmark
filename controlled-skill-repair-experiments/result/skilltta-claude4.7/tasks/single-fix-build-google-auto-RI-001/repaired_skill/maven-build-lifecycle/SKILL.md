---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Toolchain selection

Before attempting reproduction, confirm the build toolchain the project was
authored against. Legacy snapshots (for example older Google Auto / AutoValue
checkouts) commonly target **JDK 8** and Maven 3.3–3.6. Modern JDKs can break
annotation processing, `-source`/`-target` validation, and Guava internals.

Checks to perform before running Maven:

1. Inspect `.travis.yml`, `.github/workflows/*.yml`, or `Jenkinsfile` for the
   declared `jdk:` / `java-version:` and any `MAVEN_OPTS`.
2. Read the root `pom.xml` for `maven.compiler.source` / `maven.compiler.target`
   / `maven.compiler.release` and for any `<requireJavaVersion>` enforcer rule.
3. Verify the active `JAVA_HOME` (`java -version`, `mvn -v`) matches the
   project's expectation; switch toolchain before reproducing if not.
4. Note the Maven version actually invoked — plugin defaults differ across
   Maven 3.x minor releases.

Do not upgrade `source`/`target` just to make the current JDK happy; prefer
aligning the JDK to the project.

## Failure reproduction

Reproduce the failure deterministically before editing anything:

```bash
cd /home/travis/build/failed/<repo>/<id>

# Primary reproduction (covers Invoker integration tests, which only run in
# the integration-test / verify phases — never at compile).
mvn -B -V -ntp -e clean verify 2>&1 | tee /tmp/build.log

# Narrow to a single module when the reactor is large:
# mvn -B -V -ntp -e -pl <module> -am verify 2>&1 | tee /tmp/build.log

# Some legacy projects gate Invoker ITs behind a profile:
# mvn -B -V -ntp -e -Prun-its verify 2>&1 | tee /tmp/build.log
```

Key points:

- The `maven-invoker-plugin` binds to `integration-test`; `mvn compile` or
  `mvn test` will not surface Invoker failures.
- Capture the full log to `/tmp/build.log` so later `grep` passes are cheap.
- Prefer `-B -V -ntp -e` so that output is stable, versions are logged, and
  stack traces are shown on plugin errors.

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
5. Run `mvn -f <nested-pom> dependency:tree` to see what the nested build
   actually resolved (its mediation is independent of the reactor).
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

## Diagnosing dependency drift in an Invoker integration test

When a nested Invoker POM fails with `cannot find symbol` or `NoSuchMethodError`
against a common library (Guava, Truth, JUnit, jsr305, …), treat it as a
*drift-detection* problem rather than reaching for a specific version list:

1. Open the nested POM (e.g. `<module>/src/it/<name>/pom.xml`) and list its
   direct dependencies and declared versions.
2. Run `mvn -f <nested-pom> dependency:tree -Dverbose` to see which version
   each GAV actually resolved to and why.
3. Open the Invoker `build.log` under `target/it/<name>/build.log` and locate
   the *first* compiler error. The symbol it mentions implies a minimum API
   level for the owning library.
4. Cross-check that minimum against the resolved version from step 2. A
   missing symbol in a library that *is* on the classpath almost always means
   the resolved version is older than the source requires.
5. Prefer synchronizing version-coupled artifacts together (e.g. `guava` with
   `guava-testlib`) rather than bumping one in isolation.

*Illustrative example only* (do not copy blindly; verify against the repository
under repair): one historical AutoValue functional-IT drift was resolved by
synchronizing `jsr305`, `junit`, `guava` + `guava-testlib`, and `truth` to a
mutually compatible set declared directly in the nested POM. The correct set
for any given snapshot must be derived from the error log and dependency tree,
not assumed.

## Build-repair artifact contract

This benchmark requires both a diagnosis artifact and an applicable patch.
Before finishing:

1. Write `/home/travis/build/failed/failed_reasons.txt` with the reproduced
   target environment, the exact failing nested POM, the first real error, and
   the dependency-drift root cause.
2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (substituting the
   actual repository and id segments provided by the task) containing the
   intended source/configuration change.
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only
   the patch artifact—was changed.

## Minimal diagnostic sequence

```bash
cd /home/travis/build/failed/<repo>/<id>

# 1. Confirm toolchain and reactor layout.
mvn -v
find . -maxdepth 3 -name pom.xml -print

# 2. Reproduce the failure end-to-end and capture logs.
mvn -B -V -ntp -e clean verify 2>&1 | tee /tmp/build.log

# 3. If an Invoker integration build fails, inspect the nested POM and its
#    own build.log for the first concrete error.
find . -path '*/src/it/*/pom.xml' -print
find . -path '*/target/it/*/build.log' -print
# sed -n '1,180p' <module>/src/it/<name>/pom.xml
# sed -n '1,200p' <module>/target/it/<name>/build.log

# 4. Compare declared vs resolved versions in the nested build.
# mvn -f <module>/src/it/<name>/pom.xml dependency:tree -Dverbose
```

## General Maven lifecycle reminders

- In multi-module projects, use the reactor summary to identify the first
  genuinely failing module, then inspect that module's own integration steps.
- Invoker integration tests run during `integration-test`/`verify`; always
  reproduce with a phase that reaches them.
- Prefer aligning the JDK to the project rather than silently bumping
  `maven.compiler.source`/`target` to appease a newer JDK.
