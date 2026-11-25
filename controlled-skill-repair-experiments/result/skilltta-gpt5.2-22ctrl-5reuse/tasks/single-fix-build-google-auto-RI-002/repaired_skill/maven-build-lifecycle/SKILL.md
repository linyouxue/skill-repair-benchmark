---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Core rule: reproduce the target CI before changing the project

For build-repair tasks, the first successful local command is not enough. The
failure must be reproduced under the toolchain and Maven command used by the
target CI.

Before interpreting compiler/dependency errors, read the repository’s CI/build
entry points:

- CI config (`.travis.yml`, GitHub Actions workflows, etc.)
- wrapper scripts (`./mvnw`, `./gradlew`, `./ci/*.sh`, `./build.sh`)
- non-default reactor POMs (`-f <file>.xml`), profiles (`-P...`), properties

Record at least:

```bash
java -version
javac -version
mvn -version
```

### Toolchain selection is conditional on CI

If the repository declares a historical JDK and the container’s default Java is
newer, switch to the declared JDK *before* patching project files.

A failure caused only by running an old project on a modern JDK is not evidence
that the project should be migrated.

For environments that provide the BugSwarm `jdk_switcher`, you can reproduce a
CI-selected JDK **when CI explicitly requires it**. Example (CI uses OpenJDK 7):

```bash
source /opt/jdk_switcher/jdk_switcher.sh
jdk_switcher use openjdk7
export TRAVIS_JDK_VERSION=openjdk7
java -version
```

If CI uses a different JDK (e.g., 8/11/17) or a container image, mirror that
instead. Do not force JDK 7 as a default.

### Run the exact CI Maven command (do not assume one)

Run **the same Maven goals, profiles, properties, and reactor POM** that CI
runs.

Examples (pick the one that matches CI):

```bash
# Common default reactor build
mvn -B -U verify --fail-at-end

# When CI adds flags/properties (copy from CI)
mvn -B -U -Dhttps.protocols=TLSv1.2 verify --fail-at-end

# When CI uses a non-default reactor POM (only if CI does)
mvn -B -U -f <reactor-pom>.xml verify --fail-at-end
```

## Do not modernize away historical-JDK symptoms

When CI declares an old JDK (e.g., 7/8), do **not** respond to a default-JDK-11+
failure by blindly doing any of the following:

- changing Java source/target solely to make the project compile on Java 11+;
- removing or excluding `com.sun:tools` / `tools.jar` solely because Java 9+
  no longer ships it;
- adding replacement annotation APIs solely for `javax.annotation.Generated`;
- changing production logic because javac’s post-Java-8 module model produces
  different compiler-element behavior.

First reproduce on the declared JDK. Only errors that remain under the target CI
environment should drive the repair.

## Build-repair artifact contract (path must match the task prompt)

Many build-repair benchmarks require two artifacts:

1. A diagnosis write-up (path defined by the task prompt).
2. One or more patch files (path defined by the task prompt).

When the task prompt specifies a repository directory like:

`/home/travis/build/failed/<repo>/<id>`

then patch artifacts are typically required at:

`/home/travis/build/failed/<repo>/<id>/patch_1.diff` (and `patch_2.diff`, ...)

Create at least one non-empty unified diff at the required location, apply it,
and re-run the exact CI verification command.

## Minimal diagnostic sequence (template; adapt to CI)

```bash
# Use the repository path given by the task prompt
cd /home/travis/build/failed/<repo>/<id>

# 1) Establish target CI and toolchain
# (Inspect CI config and scripts; choose the JDK accordingly)
ls -la
sed -n '1,220p' .travis.yml 2>/dev/null || true

java -version
mvn -version

# 2) Reproduce the real CI command
# (Replace the following with the CI command you found)
mvn -B -U verify --fail-at-end
```

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test, Failsafe, and/or Maven Invoker steps that `test` never
  reaches.
- A green command run under the wrong JDK is not sufficient evidence of a valid
  CI repair.

## Nested test projects (Maven Invoker / integration-test fixtures)

Many Maven projects validate their build via **nested “fixture” projects** that
are *not* normal reactor modules. Common patterns include:

- `maven-invoker-plugin` running projects under `src/it`, `src/it/projects`,
  `src/it/it-*`, or a directory configured via `invoker.directory`.
- Integration tests that build “sample” projects located under `src/test/...`.

These nested projects often have their own `pom.xml` files and may fail due to
**dependency/parent resolution** differences compared to the main reactor.

### How to recognize you’re failing in a nested test project

Look for log lines such as:

- `maven-invoker-plugin:...:run`
- `Building ... (it)` or `Running ...` for each fixture project
- Errors mentioning a POM located under `src/it/.../pom.xml` (or similar)

### Common dependency/parent resolution failure modes

1) **Non-resolvable parent POM** in the fixture
- Fixture references a parent that is not available in the local repository.
- `<relativePath>` points to the wrong location (too many/few `../`).

2) **Fixture depends on reactor artifacts that were not installed**
- Invoker runs builds in separate directories; depending on configuration, the
  fixture may resolve dependencies from the local repository (or a temp local
  repository), not from the in-memory reactor.
- If CI expects `install` to have run (or expects invoker to use the current
  reactor outputs), a mismatch can cause `Could not find artifact ...`.

3) **Version mismatches / wrong coordinates**
- Fixture depends on `groupId:artifactId:version` that does not match what the
  reactor produces.
- Fixture hardcodes a version, but CI expects `${project.version}` alignment.

### Minimal diagnostic checklist for nested fixtures

1. Confirm whether the failure occurs during `verify` (Invoker/IT phase) rather
   than during `compile`/`test`.
2. Locate fixture roots:

   ```bash
   find . -path '*/src/it/*' -name pom.xml -print 2>/dev/null || true
   find . -name pom.xml -print | head
   ```

3. Identify the fixture POM that fails and inspect:
   - its `<parent>` block (coordinates + `<relativePath>`)
   - dependencies that should resolve to reactor-produced artifacts
   - any hardcoded repository URLs or profiles

4. Check the main build’s order and goals:
   - Does CI run `install` before invoker? Or only `verify`?
   - Does the invoker plugin configure a custom local repo location?

### Modification scope rules (avoid overbroad fixes)

Prefer the smallest change that matches CI intent:

- **Prefer fixing the main reactor/build configuration** so that nested fixture
  builds can resolve parents/dependencies correctly (e.g., ensure proper
  parent/module versions, ensure artifacts are available when fixtures run,
  ensure invoker config matches CI expectations).

- **Only edit fixture POMs** when the fixture itself is incorrect *and* CI
  expects fixture correctness (fixtures are part of the tested contract).
  Avoid “papering over” failures by disabling invoker/IT phases unless CI
  already provides a legitimate skip flag.

- Avoid adding new repositories, broad dependency upgrades, or JDK migrations
  unless the CI configuration indicates they are required.
