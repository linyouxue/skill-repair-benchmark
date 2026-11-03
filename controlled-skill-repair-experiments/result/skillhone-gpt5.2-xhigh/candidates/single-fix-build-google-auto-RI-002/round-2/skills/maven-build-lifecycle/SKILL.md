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

Then run the exact CI build command, including any non-default reactor POM and
flags:

```bash
# Example only — replace `-f ...` and flags with the repository's CI command.
mvn -Dhttps.protocols=TLSv1.2 -B -U -f <reactor-pom.xml> verify --fail-at-end
```

## Maven Invoker integration tests (nested projects)

Some Maven builds run integration tests via `maven-invoker-plugin` (often during
`verify`). These tests execute Maven in *nested sample projects* (commonly under
`src/it/**`). Treat these as **separate Maven builds** with their own effective POM
and (often) their own local repository.

### What is and isn't inherited

- **Dependency and plugin resolution is scoped to the nested project.**
  `dependencyManagement`, `pluginManagement`, `<repositories>`, and
  `<pluginRepositories>` from the *main* build do not apply unless the nested
  project's `pom.xml` explicitly inherits them via a `<parent>` (or imports a BOM).
- **Invoker runs may use an isolated local repository** under `target/**`.
  A missing artifact can mean it was never installed into the invoker repo, not
  that the main reactor failed to build it.
- **Parent resolution can change when projects are cloned.** Invoker typically
  copies `src/it/**` projects into `target/**` before running Maven. A `<parent>`
  `<relativePath>` that works in `src/it/...` may break after cloning, which then
  forces Maven to resolve the parent from repositories instead of the filesystem.

### Debugging flow when an invoker project fails

1. **Identify which invoker project failed** (from CI logs, `target/invoker-reports/`,
   and the per-project build logs under `target/**`).
2. Inspect the **source-controlled template** under `src/it/...` (and any
   `invoker.properties`, `settings.xml`, or profiles used for the invoker run).
3. Determine why the nested project's effective POM is missing what it needs:

   - If the error is **"version is missing"** for a dependency/plugin: the nested
     project is not inheriting the main build’s `dependencyManagement`/
     `pluginManagement`. Fix by inheriting the right parent, importing the right
     BOM, or specifying the missing versions **inside the nested project**.

   - If the error is **"could not resolve parent"**: check whether the `<parent>`
     uses a filesystem `relativePath` that will be invalid after invoker cloning.
     Typical fixes are:
     - make the invoker template self-contained (ship whatever parent POM it needs
       inside the `src/it/**` project so it is also cloned), or
     - set `<relativePath/>` and ensure the parent POM artifact is installed into
       the repository used by invoker runs.

   - If the error is **"could not resolve artifact/plugin"** that is produced by the
     current reactor (e.g. a plugin/module under test): ensure the invoker plugin
     configuration installs the required artifacts into the invoker local repo
     before running the nested builds (e.g. setup goals like `install`,
     `invoker:install`, `installArtifacts`, etc.).

4. Re-run a single invoker project for faster iteration (if supported):

```bash
mvn -pl <module-running-invoker> -Dinvoker.test=<project-pattern> -Dinvoker.streamLogs=true verify
```

### Modification scope rule for invoker tests

- **Never edit `target/**`** (cloned test projects, invoker local repositories, or
  generated reports). Those directories are regenerated; fixes must be made in the
  real module POM(s) and/or under `src/it/**` templates so they are captured in
  patches and version control.

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

1. Write your diagnosis and plan to the task-specified notes file (commonly
   `/home/travis/build/failed/failed_reasons.txt`).
2. Create at least one non-empty standard unified diff at the task-specified patch
   path (commonly `<repo_path>/patch_1.diff`) containing the intended
   source/configuration change.
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only the
   patch artifact—was changed.
5. Re-run the exact CI verification command under the CI-declared toolchain/JDK.
6. Do not finish until the full reactor, including Maven Invoker integration tests,
   succeeds.

## Minimal diagnostic sequence

```bash
REPO=/home/travis/build/failed/<repo>/<id>
cd "$REPO"

# 1. Establish target CI and toolchain.
sed -n '1,220p' .travis.yml
java -version
javac -version
mvn -version

# If CI declares a specific JDK and a switcher is available, switch first.
if [ -f /opt/jdk_switcher/jdk_switcher.sh ]; then
  source /opt/jdk_switcher/jdk_switcher.sh
  jdk_switcher use <ci-jdk>   # e.g., openjdk7
  export TRAVIS_JDK_VERSION=<ci-jdk>
fi
java -version

# 2. Reproduce the real CI command (replace with the actual command/flags).
mvn -B -U -f <reactor-pom.xml> verify --fail-at-end

```

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.
