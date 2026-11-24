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

1. Write your analysis/plan to `/home/travis/build/failed/failed_reasons.txt`.
2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (and `patch_2.diff`, ...
   if needed) containing the intended source/configuration change.
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only
   the patch artifact—was changed.
5. Re-run the exact historical CI verification command under the declared JDK.
6. Do not finish until the full reactor, including Maven Invoker integration
   tests, succeeds.

## Minimal diagnostic sequence

Bind the dynamic repository location from the task statement first, and use it
consistently for `cd`, for writing patch artifacts, and for any subsequent
inspection commands.

```bash
# Bind the target repository directory from the task:
#   /home/travis/build/failed/<repo>/<id>
REPO_DIR="/home/travis/build/failed/<repo>/<id>"
cd "$REPO_DIR"

# 1. Establish target CI and toolchain.
sed -n '1,220p' .travis.yml
source /opt/jdk_switcher/jdk_switcher.sh
jdk_switcher use openjdk7
export TRAVIS_JDK_VERSION=openjdk7
java -version
mvn -version

# 2. Reproduce the real CI command.
# (Keep -f build-pom.xml only if CI uses it.)
mvn -Dhttps.protocols=TLSv1.2 -B -U -f build-pom.xml verify \
  --fail-at-end -Dsource.skip=true -Dmaven.javadoc.skip=true

```

## Invoker / nested integration-test projects: dependency-resolution triage

Some builds run **a second Maven execution** via `maven-invoker-plugin` (or a
similar harness) against nested sample projects (often under `src/it`, `it/`,
`src/it/projects`, etc.). In that case, a dependency/plugin resolution failure
may come from the **nested project POM**, not the main reactor.

### How to tell you are in an Invoker-style failure

Look for these signals in the failing output or POMs:

- Maven logs mention `maven-invoker-plugin` goals like `run` / `install`.
- The failure references a path under `src/it/**`, `it/**`, or a copied
  directory under `target/it/**` / `target/invoker/**`.
- The error appears after the main modules build, during an integration-test
  phase.

### Decision procedure (locate the failing Maven context)

1. **Identify the failing project directory** from the log.
   - If the log points at `.../target/it/<case>/pom.xml` (a copied project),
     find the corresponding source template under `src/it/<case>/pom.xml` (or
     similar) and plan to edit the source template, not the generated copy.

2. **Inspect Invoker configuration** in the main build to find where projects
   live and how they are executed:

   ```bash
   cd "$REPO_DIR"
   rg -n "maven-invoker-plugin|invoker\." pom.xml **/pom.xml
   rg -n "<projectsDirectory>|<cloneProjectsTo>|<localRepositoryPath>" pom.xml **/pom.xml
   ```

3. **Reproduce dependency resolution in the nested project context**.
   Run Maven *from inside the nested project directory* (or with `-f` pointing
   at its `pom.xml`) so you see the same resolution behavior:

   ```bash
   # Example: run inside the nested IT project
   cd "$REPO_DIR/src/it/<case>"   # adjust to the real path
   mvn -U -e -DskipTests help:effective-pom
   mvn -U -e -DskipTests dependency:tree
   ```

4. **Classify the failure source**:
   - If `help:effective-pom` / `dependency:tree` fails in the nested project,
     the fix likely belongs to that nested project's `pom.xml` (or its parent
     reference).
   - If the nested project inherits from the main reactor (e.g., uses a parent
     from the build), confirm whether the nested project is meant to resolve
     that parent from the local reactor build or from a repository.

### Modification boundary (avoid fixing the wrong POM)

When multiple Maven contexts exist (root reactor + nested invoker projects),
apply the **most local fix that addresses the failing context**:

- Prefer editing the **nested IT project template POM** (e.g., `src/it/**/pom.xml`)
  when the error is specific to that sample project (missing repository,
  missing pluginRepository, wrong dependency version, missing `<relativePath>`
  to a parent, etc.).
- Prefer editing the **main reactor POM(s)** only when you have evidence the
  failure originates there (e.g., the invoker projects intentionally inherit
  dependencyManagement/pluginManagement from the reactor and the same
  resolution failure occurs in the reactor itself).
- Avoid broad parent-level changes (global `dependencyManagement`, repositories,
  pluginManagement) as a first response if only one invoker case fails.

This isolation reduces the risk of “fixing” the reactor while leaving the
nested invoker build broken (or vice versa).

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.
