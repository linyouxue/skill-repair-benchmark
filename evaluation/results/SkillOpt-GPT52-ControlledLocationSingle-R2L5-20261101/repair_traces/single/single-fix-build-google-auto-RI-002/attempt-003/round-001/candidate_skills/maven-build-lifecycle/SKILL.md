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

## Build-repair artifact contract

This benchmark requires both a diagnosis artifact and an applicable patch.
Before finishing:

2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/google/auto/patch_1.diff` (or the repository path
   given by the task) containing the intended source/configuration change.
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only
   the patch artifact—was changed.
5. Re-run the exact historical CI verification command under JDK 7.
6. Do not finish until the full reactor, including Maven Invoker/integration-test fixture projects executed during `verify`, succeeds.
   - If the failure is in a nested fixture (e.g., `src/it/**`), ensure you repaired the correct scope (fixture POM/config vs inherited parent management).

## Minimal diagnostic sequence



## Nested test projects / Invoker fixtures: how to diagnose and where to fix

Many legacy builds execute *embedded Maven projects* during `verify` (Maven Invoker Plugin, integration-test fixtures, sample apps). Dependency resolution failures may occur **inside those nested projects**, not in the main reactor.

### 1) Identify when the failure is from a nested project (not the main reactor)

Look for telltales in the console output:

- Maven Invoker Plugin messages such as `maven-invoker-plugin` / `Invoking Maven` / `Running .../src/it/...`.
- Paths pointing under fixture directories (common patterns):
  - `src/it/**` (Invoker IT projects)
  - `src/test/resources/**` with embedded `pom.xml`
  - `it/**`, `integration-tests/**`, `samples/**`, `examples/**`
- Errors mentioning a `pom.xml` *not* at the reactor root (e.g., `.../src/it/foo/pom.xml`).

If the stack trace or error path references a fixture directory, treat it as a nested-project failure until proven otherwise.

### 2) Reproduce and inspect nested-project failures

- Run the **same phase that triggers the fixtures** (typically `mvn ... verify`, not just `test`).
- Re-run with more diagnostics for resolution issues:

```bash
mvn -f build-pom.xml verify -e -X -U --fail-at-end \
  -Dsource.skip=true -Dmaven.javadoc.skip=true
```

- Inspect Invoker output directories after failure (paths vary by plugin config, but commonly):
  - `target/invoker/**` (project copies)
  - `target/invoker-reports/**` or `target/it/**` (reports)
  - `target/failsafe-reports/**` (if driven via Failsafe)

Search for the failing nested POM and its captured Maven logs:

```bash
find . -path '*target*invoker*' -o -path '*target*failsafe-reports*' | head
find . -path '*src/it*' -name pom.xml
```

Also confirm whether the failure depends on repository state:

- Some ITs rely on artifacts built earlier in the same build. If the build uses `-Dmaven.repo.local=...` in CI, reproduce with it.
- If resolution seems inconsistent, verify `~/.m2/repository` is not contaminated (but avoid deleting it blindly; prefer using a temporary local repo if needed).

### 3) Dependency-management boundaries for nested projects

Nested projects may be:

- **Inherited fixtures**: they point to a parent in the main repo (via `<parent>` referencing the reactor or an installed parent), and thus inherit `dependencyManagement` / `pluginManagement`.
- **Standalone fixtures**: they have their own coordinates and do *not* inherit the main reactor’s parent/management; they may intentionally test external-consumer behavior.

Before changing anything, open the nested fixture `pom.xml` and determine:

- Does it declare `<parent>`? If yes, is that parent the same as the reactor parent (and will it be resolvable during the IT run)?
- Does it rely on `${project.version}` from the outer build, or hard-coded versions?
- Does it use plugins with versions coming from `pluginManagement`, or does it require explicit plugin versions locally?

### 4) Decision rule: where to apply fixes

Apply the **smallest-scope change** that makes the failing Maven execution succeed:

- If the nested project **inherits** the parent management that is wrong/missing, fix it in the *shared* parent `dependencyManagement`/`pluginManagement`.
- If the nested project is **standalone** (no inheritance from the reactor parent, or intended to be independent), fix **only the fixture** (`src/it/.../pom.xml`, its settings, or its invoker config). Do *not* patch unrelated reactor modules.
- If the failure is due to a missing artifact that should be produced by the reactor, verify the build actually installs/builds it before the invoker step (ordering, `install` vs `verify`, profiles). Prefer adjusting the invoker execution configuration rather than broad reactor refactors.

### 5) Modification-scope constraints (avoid over-fixing)

When only a nested IT/fixture is broken:

- Do **not** modernize the overall build (parent version bumps, plugin upgrades, dependency refreshes) unless the nested fixture inherits those and the change is required.
- Do **not** refactor unrelated modules to "make the build nicer".
- Prefer targeted changes: add an explicit dependency version in the fixture, add a missing repository entry only where needed, or align a plugin version used by the fixture.
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

```

## General Maven lifecycle reminders



- Failures reported during `verify` may come from *nested Maven executions* (Invoker / sample projects). Always confirm which `pom.xml` Maven was executing when resolution failed.
- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.
