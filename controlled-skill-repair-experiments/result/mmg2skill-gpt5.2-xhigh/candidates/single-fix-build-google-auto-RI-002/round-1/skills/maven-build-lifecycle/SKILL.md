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

Then run the exact CI build command, including any non-default reactor POM:

```bash
mvn -Dhttps.protocols=TLSv1.2 -B -U -f build-pom.xml verify \
  --fail-at-end -Dsource.skip=true -Dmaven.javadoc.skip=true
```

### Maven Invoker / nested test projects: fix the template POMs, not generated copies

If the build fails while running Maven Invoker (or any integration test that
builds “nested projects”), treat those nested projects as **real builds with
their own dependency resolution**:

- Identify where the nested projects are sourced from (commonly `src/it/**`,
  `src/test/resources/**`, or a dedicated `it/` directory).
- Apply dependency/plugin/version fixes to the **source templates** under the
  repository, not to generated directories under `target/**` (those will be
  recreated on every run).
- If the top-level build succeeds but invoker projects fail to resolve deps,
  inspect the nested project `pom.xml` and its parent/repository settings; it
  may not inherit the same dependencyManagement/pluginManagement as the reactor.

### Do not modernize away historical-JDK symptoms

When CI declares an old JDK (e.g., JDK 7), do **not** respond to a default-JDK-11
failure by blindly doing any of the following:

- changing Java source/target solely to make the project compile on Java 11;
- removing or excluding `com.sun:tools` / `tools.jar` solely because Java 9+
  no longer ships it;
- adding replacement annotation APIs solely for `javax.annotation.Generated`;
- changing production logic because javac's post-Java-8 module model produces
  different compiler-element behavior.

First reproduce on the declared JDK. Only errors that remain under the target
CI environment should drive the repair. (Conversely, if CI is already on Java 9+,
then `tools.jar`/system-scope issues are genuine build breakages to fix.)

## Build-repair artifact contract (must satisfy for evaluation)

This benchmark requires both a diagnosis artifact and an applicable patch.
Create these artifacts early (right after you have a reproducible failure),
not at the end.

1. Write a non-empty diagnosis + plan to:
   `/home/travis/build/failed/failed_reasons.txt`
2. Create at least one non-empty unified diff at:
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff`
   (increment `patch_{i}.diff` if you need multiple patches)
   - Prefer generating patches via `git diff > patch_1.diff` so you don’t have to
     hand-author multi-line diff content.
3. Ensure the repository working tree actually reflects the patch (not only the
   patch artifact):
   - verify with `git status` and `git diff --stat`
4. Re-run the exact CI verification command (same JDK, same Maven flags, same
   reactor POM) until it succeeds, including any Maven Invoker integration tests.

## Minimal diagnostic sequence (run each command separately)

The execution tool in this environment may reject multi-line / multi-command
blocks; run commands one-at-a-time.

1. Enter the repository (use the task-provided `<repo>/<id>` path):
   ```bash
   cd /home/travis/build/failed/<repo>/<id>
   ```
2. Inspect CI config to find the real build command and JDK:
   ```bash
   ls -la
   ```
   ```bash
   sed -n '1,220p' .travis.yml
   ```
3. Record tool versions (paste these into `failed_reasons.txt`):
   ```bash
   java -version
   ```
   ```bash
   javac -version
   ```
   ```bash
   mvn -version
   ```
4. Reproduce the failure with the CI command. If the environment is offline or
   dependencies are expected to come from the local cache, also try an offline
   run to get actionable “missing artifact/plugin” coordinates:
   ```bash
   mvn -o -B -e verify --fail-at-end
   ```
5. Locate the source of the error:
   - For missing artifact/plugin coordinates: check whether it’s a **build plugin**
     resolution issue vs a normal dependency issue (plugins resolve too).
   - For “file not found” / `systemPath` breakage: grep the repository for the
     failing coordinate/path string (e.g., `tools.jar`).
   - If you suspect offline-cache gaps, confirm what is and isn’t present under
     `~/.m2/repository/` to narrow the failure.
6. Immediately write/update the required diagnosis+plan file:
   - Use a one-liner write so you don’t need multi-line shell blocks:
     ```bash
     printf '%s\n' \
       "Repro command: <paste exact mvn command>" \
       "Observed failure: <paste key Maven error lines>" \
       "Root cause guess: <code vs build config?>" \
       "Plan: <files to change + why>" \
       > /home/travis/build/failed/failed_reasons.txt
     ```

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.
