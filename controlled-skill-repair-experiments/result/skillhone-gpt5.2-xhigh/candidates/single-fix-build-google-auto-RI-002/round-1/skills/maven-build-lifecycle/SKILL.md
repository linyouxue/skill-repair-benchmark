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

For environments that provide the BugSwarm JDK switcher, a Travis build that
pins an older JDK can be reproduced with (example for JDK 7):

```bash
source /opt/jdk_switcher/jdk_switcher.sh
jdk_switcher use openjdk7
export TRAVIS_JDK_VERSION=openjdk7
java -version
```

Then run the **exact** CI build command. If CI uses a non-default reactor POM
(`-f ...`) or extra properties, include them.

Example pattern (do **not** copy blindly; take the real command from CI):

```bash
mvn -B -U -f <reactor-pom>.xml verify --fail-at-end
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

1. Write your analysis and plan to the path requested by the task (often
   `/home/travis/build/failed/failed_reasons.txt`).
2. Create at least one non-empty standard unified diff at the path requested by
   the task (e.g. `/home/travis/build/failed/<repo>/<id>/patch_1.diff`) containing
   the intended source/configuration change.
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only
   the patch artifact—was changed.
5. Re-run the exact historical CI verification command under the declared
   JDK/toolchain.
6. Do not finish until the full reactor, including Maven Invoker integration
   tests, succeeds.

## Minimal diagnostic sequence

```bash
cd /home/travis/build/failed/<repo>/<id>  # use the path given by the task

# 1. Establish target CI and toolchain.
sed -n '1,220p' .travis.yml

# If CI pins an older JDK and the environment provides jdk_switcher, switch
# before patching project files. Example:
source /opt/jdk_switcher/jdk_switcher.sh
jdk_switcher use openjdk7
export TRAVIS_JDK_VERSION=openjdk7

java -version
mvn -version

# 2. Reproduce the real CI command (copy it from CI config).
# Example pattern:
mvn -B -U -f <reactor-pom>.xml verify --fail-at-end
```

## Maven Invoker integration tests: nested IT projects and dependency scope

If the build runs Maven Invoker integration tests (`maven-invoker-plugin`),
Maven will execute additional Maven builds against nested “IT projects” (often
under `src/it/**`), sometimes using a dedicated local repository and/or settings
file.

Key implications:

- A dependency resolution error during an invoker run is often coming from the
  nested IT project's own `pom.xml` (plus any invoker `settings.xml`), not the
  root reactor POM.
- Invoker commonly clones IT projects into `target/**` (e.g. `target/it`,
  `target/invoker`, `target/invoker-reports`) before running Maven. Do **not**
  edit the cloned copies under `target/` — they are generated and will be
  wiped/recreated. Patch the source IT project under the configured
  `projectsDirectory` (commonly `src/it/`) instead.

Checklist:

1. Find the invoker configuration in the reactor (`pom.xml`):
   - locate `<artifactId>maven-invoker-plugin</artifactId>`
   - note `<projectsDirectory>`, `<cloneProjectsTo>`, `<localRepositoryPath>`,
     `<settingsFile>`, `<filterPropertiesFile>`, and any `invoker.properties`
     conventions
2. When the invoker run fails, identify the failing IT project:
   - the console output and/or `target/invoker-reports/**` usually include the
     failing project directory and the Maven command it ran
   - map any `target/.../<it-project>` path back to the source directory under
     `<projectsDirectory>`
3. Reproduce the failing IT build in isolation (faster iteration):
   - run Maven from the IT project's *source* directory using the same
     goals/profiles
   - if invoker uses a dedicated local repo/settings, pass them explicitly
     (`-Dmaven.repo.local=...` and `-s ...`) so dependency resolution matches the
     invoker environment
4. Apply the fix at the correct layer:
   - missing dependency/plugin repo only in the IT project → edit that IT
     project's `pom.xml` / `settings.xml` / `invoker.properties`
   - IT projects cannot resolve artifacts built in the main reactor → ensure
     those artifacts are available to the repository the invoker run uses
     (commonly by making sure the build installs them into the invoker local repo
     before `invoker:run`)

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.
- When diagnosing invoker failures, prefer the per-project logs under
  `target/invoker-reports/` (or the directory configured by the plugin) over
  guessing based on the top-level reactor output.
