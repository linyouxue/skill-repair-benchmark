---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Core rule: reproduce the target CI before changing the project

For build-repair tasks, the first successful local command is not enough. The
failure must be reproduced under the toolchain and Maven command used by the
target CI. Read the repository's CI configuration (`.travis.yml`, workflow
files, wrapper scripts, build POMs) before interpreting any compiler or
dependency error.

Record at least:

```bash
java -version
javac -version
mvn -version
```

If the repository declares a historical JDK and the container's default Java
is newer, switch to the declared JDK *before* patching project files. A failure
caused only by running an old project on a modern JDK is not evidence that the
project should be migrated.

For environments that provide the BugSwarm JDK switcher, a JDK 7 Travis build
can be reproduced with:

```bash
source /opt/jdk_switcher/jdk_switcher.sh
jdk_switcher use openjdk7
export TRAVIS_JDK_VERSION=openjdk7
java -version
```

Then run the exact CI build command, including any non-default reactor POM:

```bash
mvn -Dhttps.protocols=TLSv1.2 -B -U -f build-pom.xml verify \
  --fail-at-end -Dsource.skip=true -Dmaven.javadoc.skip=true
```

### Do not modernize away historical-JDK symptoms

When CI declares JDK 7, do **not** respond to a default-JDK-11 failure by
blindly doing any of the following:

- changing Java source/target solely to make the project compile on Java 11;
- removing or excluding `com.sun:tools` / `tools.jar` solely because Java 9+
  no longer ships it;
- adding replacement annotation APIs solely for `javax.annotation.Generated`;
- changing production logic because javac's post-Java-8 module model produces
  different compiler-element behavior.

First reproduce on the declared JDK. Only errors that remain under the target
CI environment should drive the repair.

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
5. If useful, run `dependency:tree` against the nested POM under the same JDK.
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

The functional-test dependency block is stale relative to the intended
AutoValue integration-test project. The observed failure is a test-compilation
error for `com.google.common.base.MoreObjects`, so repairing Java 11
compatibility elsewhere is the wrong failure class.

Synchronize this functional-test POM as one coherent dependency repair:

- `com.google.code.findbugs:jsr305` -> `3.0.0` (`provided`);
- `junit:junit` -> `4.12` (`test`);
- add a direct `com.google.guava:guava:19.0` test dependency;
- `com.google.guava:guava-testlib` -> `19.0` (`test`);
- `com.google.truth:truth` -> `0.28` (`test`).

Keep the repair scoped to the functional integration-test POM unless the
target-JDK reproduction exposes an additional independent failure. Do not
change the repository-wide Java language level for this defect.

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
5. Re-run the exact historical CI verification command under JDK 7.
6. Do not finish until the full reactor, including Maven Invoker integration
   tests, succeeds.

## Minimal diagnostic sequence

```bash
cd /home/travis/build/failed/google/auto

# 1. Establish target CI and toolchain.
sed -n '1,220p' .travis.yml
source /opt/jdk_switcher/jdk_switcher.sh
jdk_switcher use openjdk7
export TRAVIS_JDK_VERSION=openjdk7
java -version
mvn -version

# 2. Reproduce the real CI command.
mvn -Dhttps.protocols=TLSv1.2 -B -U -f build-pom.xml verify \
  --fail-at-end -Dsource.skip=true -Dmaven.javadoc.skip=true

# 3. If AutoValue's Invoker functional build fails, inspect the nested POM.
sed -n '1,180p' value/src/it/functional/pom.xml
find value/target/it -name build.log -print

# 4. Make the narrow dependency-sync repair, create/apply the required patch,
#    and then repeat step 2 under the same JDK.
```

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- In multi-module projects, use the reactor summary to identify the first
  genuinely failing module, then inspect that module's own integration steps.
- Prefer a narrow root-cause repair over broad dependency exclusions or
  toolchain migrations.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.

