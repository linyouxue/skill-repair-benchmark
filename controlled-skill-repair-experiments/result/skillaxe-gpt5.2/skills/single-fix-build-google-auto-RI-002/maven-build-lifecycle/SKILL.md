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

## Build-repair artifact contract (do not skip)

Many build-repair benchmarks require **specific artifacts in specific paths**.
Do not rely on examples from other repos.

Before finishing, ensure all of the following are true:

1. **Diagnosis note exists**: write your Step 1 analysis + plan to:
   - `/home/travis/build/failed/failed_reasons.txt`

2. **Patch artifact(s) exist**: create at least one non-empty **standard unified diff** file
   under the task’s repository directory:
   - `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (and `patch_2.diff`, etc. if needed)

   Recommended way to guarantee correct diff format:

   ```bash
   # after editing files
   git diff > patch_1.diff
   ```

3. **Patch is applied to the working tree**: confirm the intended project file—not only the
   patch artifact—was changed.

   ```bash
   git status
   git diff --stat
   ```

4. **Re-run the exact CI command** under the declared JDK/toolchain until green.

5. If the build uses **Maven Invoker integration tests**, do not stop at a green `test`.
   Run the full `verify` (or the CI’s exact command) so Invoker runs too.

## Minimal diagnostic sequence (parameterized)

> Replace `<repo>` and `<id>` with the task-provided values.

```bash
cd /home/travis/build/failed/<repo>/<id>

# 1. Establish target CI and toolchain.
# (Travis example)
[ -f .travis.yml ] && sed -n '1,220p' .travis.yml || true

# If the CI declares a historical JDK, switch before diagnosing.
if [ -f /opt/jdk_switcher/jdk_switcher.sh ]; then
  source /opt/jdk_switcher/jdk_switcher.sh
fi

java -version
javac -version || true
mvn -version

# 2. Reproduce the real CI command.
# Prefer the repo's documented command; otherwise try the CI's.
# Example (only if the repo uses a non-default reactor POM):
# mvn -Dhttps.protocols=TLSv1.2 -B -U -f build-pom.xml verify --fail-at-end
```

## Maven Invoker / nested test projects: dependency-resolution boundaries

Multi-module builds sometimes run **nested Maven builds** via `maven-invoker-plugin`
(or similar tooling) during `integration-test`/`verify`. Those nested projects often
live under directories like `src/it/**`, `invoker/**`, `integration-tests/**`, etc.

When a failure looks like *dependency resolution* (e.g., “Could not resolve artifact …”)
and it occurs during Invoker execution, apply this decision procedure **before editing POMs**:

1. **Confirm where the failure originates**
   - Determine whether the error is from the main reactor build or from an Invoker-launched
     nested build.
   - Look for log markers such as Invoker goals, “Running Maven … in …/src/it/...”, or
     separate Maven executions.

2. **Inspect Invoker configuration first (preferred fix surface)**
   - Check the `maven-invoker-plugin` configuration in the effective POM:

     ```bash
     mvn -q help:effective-pom -DforceStdout | sed -n '1,200p'
     ```

   - Typical knobs that affect nested dependency resolution:
     - `settingsFile` / `mavenHome` / `localRepositoryPath`
     - `cloneProjectsTo` / `projectsDirectory`
     - `goals` and any `-Dmaven.repo.local=...` usage

   If the nested build is unintentionally using a different local repo/settings than CI,
   fix the Invoker configuration (or CI config) rather than patching every nested POM.

3. **Prefer fixing dependency versions at the highest shared level**
   - If nested projects are intended to inherit from the main reactor (parent POM/BOM),
     fix versions in the parent `dependencyManagement` / BOM so both reactor and nested
     builds resolve consistently.
   - Only modify a nested test project POM when:
     - it is intentionally standalone (no parent link to the reactor), AND
     - the test is specifically validating behavior with that dependency set.

4. **Avoid overfitting by editing many nested fixtures**
   - Editing multiple `src/it/**/pom.xml` files is usually a smell.
   - If many fixtures fail the same way, the root cause is often:
     - a missing repository definition/settings propagation,
     - a missing pluginRepository,
     - a missing dependencyManagement entry,
     - or a property/version not being passed into the nested build.

5. **Validate with targeted reproduction**
   - Re-run the exact `verify` that triggers Invoker.
   - If needed, reproduce a single failing Invoker project by running Maven in that
     directory with the same flags/settings the Invoker uses.

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.
