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

## Classifying the failure locus: parent reactor vs nested Invoker child

Before proposing any edit, decide whether the failure surfaces in the main
reactor module or inside a nested build driven by `maven-invoker-plugin`
(a common pattern for annotation-processor projects such as AutoValue /
AutoService, where `src/it/<case>/` holds self-contained Maven test projects
that the parent build invokes). The patch target depends entirely on this
classification, and getting it wrong wastes the repair budget on the wrong
file.

### How to detect a nested Invoker failure

In the CI log, look for any of the following signals:

- `[INFO] Building: <case>/pom.xml` emitted by `maven-invoker-plugin` (as
  opposed to the standard reactor banner `[INFO] Building <artifact> <ver>`);
- a `BUILD FAILURE` whose stack trace or `BUILD LOG` section references a path
  under `src/it/<case>/` or under `target/it/<case>/`;
- goal `invoker:install`, `invoker:integration-test`, or `invoker:verify`
  being the step that reports the failure;
- a message pointing at a `build.log` file inside the invoked project
  directory, e.g. `target/it/<case>/build.log`.

In the repository, confirm by inspecting the invoker configuration in the
failing module's `pom.xml` (typical keys: `projectsDirectory` — usually
`src/it` — `localRepositoryPath` — usually `target/it-repo` or
`target/local-repo` — and `settingsFile`).

### How the invoked child resolves dependencies

A nested Invoker project is a *separate* Maven build. It does **not**
automatically see the parent's `<dependencyManagement>` or `<dependencies>`.
Its dependency resolution rules are:

1. The child reads its own `pom.xml` under `src/it/<case>/pom.xml`
   (often filtered through `${project.version}` style tokens from the
   invoker configuration).
2. The child resolves artifacts from the **invoker-provided local repository**
   (the `localRepositoryPath` above), which the parent populates during
   `invoker:install` with the just-built artifacts of the reactor.
3. Per-case overrides live in `src/it/<case>/invoker.properties`
   (e.g. `invoker.goals`, `invoker.mavenOpts`, `invoker.java.version`,
   `invoker.buildResult`).
4. Anything the child needs that the parent did not install into the invoker
   local repo must be declared in the child's own `pom.xml` or injected via
   `invoker.properties` / the invoker `settingsFile`.

Consequently, a repair for an Invoker-level failure typically edits files
**inside the nested test project**, not the parent module:

- missing/incorrect dependency, plugin version, or `<build>` configuration →
  edit `src/it/<case>/pom.xml`;
- wrong goals, JDK gate, or expected outcome → edit
  `src/it/<case>/invoker.properties`;
- missing or outdated expected source/resource → edit files under
  `src/it/<case>/src/...`.

Only edit the parent module when the failure is clearly in the parent build
(e.g. the artifact installed into the invoker local repo is itself wrong, or
the invoker-plugin configuration in the parent `pom.xml` is misdeclared).

This nested-project triage still runs **under the declared historical JDK**;
the JDK switcher step above is a prerequisite, not an alternative.

## Build-repair artifact contract

This benchmark requires both a diagnosis artifact and an applicable patch.
Before finishing:

1. Classify the failure locus using the section above (parent reactor vs
   nested Invoker child) and record that classification in
   `failed_reasons.txt`.
2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (use the actual repo
   path given by the task, e.g. `.../google/auto/patch_1.diff`). The diff's
   `a/` and `b/` paths — and the files it actually touches — must correspond
   to the failing unit:
   - parent-reactor failure → files under the parent module
     (`pom.xml`, `src/main/...`, `src/test/...`, `build-pom.xml`, etc.);
   - nested Invoker failure → files inside the nested test project
     (`<module>/src/it/<case>/pom.xml`,
     `<module>/src/it/<case>/invoker.properties`,
     `<module>/src/it/<case>/src/...`), **not** the parent module by default.
   Do not default to the repository root just because that is where the diff
   artifact lives.
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file — at the
   correct scope identified in step 1, not only the patch artifact — was
   changed.
5. Re-run the exact historical CI verification command under the declared JDK
   (e.g. JDK 7).
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

### Nested Invoker test projects — targeted diagnostics

When the step above fails inside `maven-invoker-plugin`, add:

```bash
# a. Identify the failing module and inspect its invoker configuration.
grep -R --include=pom.xml -n 'maven-invoker-plugin' .

# b. List nested integration-test projects and their per-case overrides.
ls -1 <module>/src/it
find <module>/src/it -maxdepth 2 -name pom.xml -o -name invoker.properties

# c. Read the invoked child's own build log — this is the authoritative error,
#    not the parent reactor summary.
sed -n '1,400p' <module>/target/it/<case>/build.log

# d. Inspect the invoker-provided local repository used by the child build.
ls <module>/target/it-repo 2>/dev/null || ls <module>/target/local-repo 2>/dev/null
```

Use the child `build.log` to decide whether the fix belongs in the nested
`pom.xml`, the nested `invoker.properties`, nested sources, or (less often)
the parent configuration that installs artifacts into the invoker local repo.

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.
- A nested Invoker child build has its own POM, its own local repository, and
  its own effective settings; do not assume the parent reactor's dependency
  graph covers it.

