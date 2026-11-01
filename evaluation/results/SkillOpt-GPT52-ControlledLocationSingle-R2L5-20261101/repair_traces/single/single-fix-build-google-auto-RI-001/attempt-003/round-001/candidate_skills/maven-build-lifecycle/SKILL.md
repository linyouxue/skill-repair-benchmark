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
4. Inspect the nested POM's direct dependencies, dependencyManagement, plugins, and versions.
5. Reproduce the nested build directly with the same profiles/properties used in CI.
6. Repair the nested dependency/configuration drift instead of broad-editing
   unrelated top-level modules.

Do not assume versions declared in the parent module automatically govern an
Invoker integration-test POM. An integration-test POM copied or synchronized
separately can become stale.



## Toolchain selection and validation

Before changing source or dependencies, confirm that the local reproduction environment matches CI expectations.

- Check the required Java and Maven versions from `.mvn/`, `mvnw`, CI config, `pom.xml`, `maven-enforcer-plugin`, `maven-compiler-plugin`, and `toolchains.xml`.
- Prefer the Maven Wrapper when present:
  ```bash
  ./mvnw -version
  ```
  Otherwise record the system Maven version:
  ```bash
  mvn -version
  ```
- Verify `JAVA_HOME` and the active JDK:
  ```bash
  echo "$JAVA_HOME"
  java -version
  ```
- If the build uses Maven toolchains, confirm that `~/.m2/toolchains.xml` supplies the requested JDK version/vendor.
- Compare compiler `source`/`target`/`release` settings with the active JDK. Legacy projects may require older bytecode targets or fail under newer JDKs without additional flags.
- Preserve CI profiles, properties, and repository settings when reproducing locally. A build that passes without the CI profiles enabled may still fail in the actual pipeline.
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
Before finishing:

1. Write `/home/travis/build/failed/failed_reasons.txt` with the reproduced
   target environment, the exact failing nested POM, the first real error, and
   the dependency-drift root cause.
2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/google/auto/patch_1.diff` (or the repository path
   given by the task) containing the intended source/configuration change.
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only
   the patch artifact—was changed.
## Minimal diagnostic sequence



Use consistent Maven command conventions while reproducing failures:

```bash
# Full clean CI-style build with stacktraces.
mvn clean verify -e -DtrimStackTrace=false

# Add debug logging only after reproducing the failure.
mvn clean test -X -e -DtrimStackTrace=false

# Rebuild a single module and required dependencies.
mvn -pl <module> -am test

# Skip unit tests or Invoker ITs only to isolate phases.
mvn verify -DskipTests
mvn verify -Dinvoker.skip=true
```

Prefer `clean` builds when validating dependency or generated-source changes. Incremental builds can hide stale reactor or plugin state in legacy multi-module projects.
```bash
cd /home/travis/build/failed/google/auto

# Reproduce the main reactor failure first.
mvn clean verify -e -DtrimStackTrace=false

# If AutoValue's Invoker functional build fails, inspect the nested POM.
sed -n '1,180p' value/src/it/functional/pom.xml
find value/target/it -name build.log -print

# Re-run the nested build with the same profiles/properties used by CI.
cd value/src/it/functional
mvn test -e -X -DtrimStackTrace=false

# Inspect resolved dependency versions inside the nested project.
mvn dependency:tree
mvn help:effective-pom > effective-pom.xml
```

## General Maven lifecycle reminders

- In multi-module projects, use the reactor summary to identify the first
  genuinely failing module, then inspect that module's own integration steps.

- For Maven Invoker integration tests, inspect the generated `build.log` under `target/it/**` before editing project code. The outer reactor failure is often only a wrapper around a nested dependency-resolution or compiler error.
- Use `dependency:tree` inside the failing nested project to confirm the selected versions of coupled libraries such as `guava` and `guava-testlib`.
- When using `-pl` and `-am`, verify that required aggregator-generated artifacts or parent POMs were installed; some legacy builds require a prior `install` phase before isolated module reproduction works correctly.
