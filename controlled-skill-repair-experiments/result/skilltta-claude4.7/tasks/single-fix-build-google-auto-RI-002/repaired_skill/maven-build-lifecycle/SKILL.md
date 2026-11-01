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

Then run the exact CI build command. **Detect the reactor POM from the CI
config** rather than assuming a filename: inspect `.travis.yml` (`script:`,
`install:`, env vars) and any wrapper scripts for an explicit `-f <pom>` flag.
Fall back order when nothing is declared: `pom.xml`, then `build-pom.xml` if it
exists at the repo root. Preserve every flag the CI used (profiles, `-U`,
`-B`, `-Dhttps.protocols=...`, skip flags). Example when CI declares
`build-pom.xml`:

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
The task prompt specifies the repository path as
`/home/travis/build/failed/<repo>/<id>` where `<id>` is a distinct subdirectory
(e.g., a BugSwarm image id). Patch artifacts must live under that same
`<repo>/<id>` directory. Before finishing:

1. Write analysis to `/home/travis/build/failed/failed_reasons.txt`.
2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (additional patches as
   `patch_2.diff`, ...) containing the intended source/configuration change.
   Do **not** hard-code any project name such as `google/auto` into this path —
   always substitute the actual `<repo>/<id>` from the task prompt.
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only
   the patch artifact—was changed.
5. Re-run the exact historical CI verification command under the declared JDK.
6. Do not finish until the full reactor, including Maven Invoker integration
   tests, succeeds.

## Scoping fixes to nested test projects

Multi-module Maven repos frequently route failures through **nested reactors**
that are not part of the top-level `<modules>` list:

- Maven Invoker IT projects under `src/it/<name>/pom.xml` (invoked by
  `maven-invoker-plugin` during `integration-test`).
- Dedicated `*-tests` / `compile-tests` modules that exercise annotation
  processors or generated code.
- `src/test/resources/projects/*` fixtures used by plugin ITs.

When a failure originates inside one of these nested projects:

- Edit **that nested pom** (its own `<dependencies>`,
  `<dependencyManagement>`, `<build>/<plugins>`, `annotationProcessorPaths`,
  scope/version overrides). The nested Invoker project typically does **not**
  inherit from the outer reactor, so changes to the root pom will not reach it.
- Only touch the parent / BOM when the same fix must apply to multiple
  modules, or when the nested pom explicitly inherits management from a
  shared parent that is in scope at Invoker execution time.
- Preserve the nested project's declared parent and `<relativePath>`; do not
  rewire it to the outer reactor just to share dependency management.
- When adding a dependency a nested IT needs, prefer versions already pinned
  in the surrounding repo (parent properties, existing dependency entries) so
  the Invoker run stays consistent with the main build.

## Minimal diagnostic sequence

Substitute `<repo>/<id>` with the path from the task prompt — never hard-code
a specific project.

```bash
cd /home/travis/build/failed/<repo>/<id>

# 1. Establish target CI and toolchain.
sed -n '1,220p' .travis.yml
source /opt/jdk_switcher/jdk_switcher.sh
jdk_switcher use openjdk7      # or whatever .travis.yml declares
export TRAVIS_JDK_VERSION=openjdk7
java -version
mvn -version

# 2. Identify the reactor POM declared by CI (grep for '-f ' in .travis.yml
#    and any wrapper scripts). Fall back to pom.xml, then build-pom.xml.

# 3. Reproduce the real CI command verbatim, e.g.:
mvn -Dhttps.protocols=TLSv1.2 -B -U -f build-pom.xml verify \
  --fail-at-end -Dsource.skip=true -Dmaven.javadoc.skip=true
```

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.
- The historical CI verify command is the finishing criterion for this
  benchmark; `skilltta-task-guidance` defers to it rather than overriding it.
