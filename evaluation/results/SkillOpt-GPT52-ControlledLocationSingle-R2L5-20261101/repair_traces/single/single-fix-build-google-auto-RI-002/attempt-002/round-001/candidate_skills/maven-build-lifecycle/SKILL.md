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

```

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.



## Nested Maven integration-test projects and Invoker fixtures

Many legacy Maven repositories contain nested test builds under paths such as
`src/it/**`, `integration-tests/**`, or directories referenced by
`maven-invoker-plugin`, the Maven Verifier, or custom integration-test
scripts. These fixture projects are often executed as independent Maven builds
during `verify` and may not inherit the root reactor's dependencyManagement,
repositories, pluginManagement, or active profiles.

Before changing a top-level POM, determine whether the failing dependency or
plugin resolution occurs inside a nested fixture project:

```bash
find . -path '*src/it*' -name pom.xml
grep -R "maven-invoker-plugin\|Verifier" -n .
```

When reproducing fixture failures, run Maven from the fixture directory or use
its exact Invoker configuration instead of assuming the root reactor state:

```bash
cd src/it/sample-project
mvn -e -X verify
mvn help:effective-pom
mvn dependency:tree
```

Check how the fixture resolves its parent POM and repositories. A nested test
project may:

- inherit from a published parent instead of the current checkout;
- use `<relativePath/>` rules that bypass the local reactor;
- require `mvn install` of a parent or plugin before the fixture can resolve;
- use a separate local repository configured by the Invoker plugin or CI.

Reproduce dependency resolution with the same mirrors, settings.xml, local
repository location, and command-line flags used by CI. A fixture that passes
only because it accidentally consumed artifacts from the developer's local
repository is not a valid repair.

Modification scope matters:

- Prefer fixing dependency versions, exclusions, scopes, repositories, or test
  fixture configuration inside the nested project when the failure is isolated
  there.
- Change root `dependencyManagement`, `pluginManagement`, or shared reactor
  configuration only after confirming the dependency ownership originates from
  the main build and affects multiple modules.
- Avoid blanket exclusions or unrelated global dependency upgrades when only a
  single Invoker fixture fails.

Examples:

- Correct: update a dependency version in `src/it/.../pom.xml` when only the
  Invoker fixture cannot resolve it.
- Correct: install the parent artifact locally or fix `<relativePath>` when
  the fixture expects a parent outside the reactor.
- Incorrect: add a global exclusion in the root POM before verifying the
  failing dependency is actually inherited from the root build.
