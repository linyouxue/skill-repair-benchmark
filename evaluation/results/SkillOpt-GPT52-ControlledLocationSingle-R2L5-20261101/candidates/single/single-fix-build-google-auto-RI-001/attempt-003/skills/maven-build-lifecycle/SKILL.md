---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Maven Invoker failures: debug the nested project, not just the reactor

`maven-invoker-plugin` can launch independent Maven builds from files such as
`src/it/*/pom.xml`. Those nested builds have their own dependency mediation and
can fail even when the parent module's normal unit tests pass.

If Maven reports output similar to:

```text
The following builds failed:
*  functional/pom.xml
```

then:

1. Locate the exact integration-test POM named by the Invoker.
2. Read the corresponding Invoker `build.log` or the surrounding CI output.
3. Identify the *first concrete compiler/test error* inside that nested build.
4. Inspect the nested POM's direct dependencies, dependencyManagement, plugins, and versions.
5. Reproduce the nested build directly with the same profiles/properties used in CI.
6. Repair the nested dependency/configuration drift instead of broad-editing
   unrelated top-level modules.



**Reproduction rule:** treat the Invoker output as a pointer. Always open the corresponding `target/it/**/build.log` and reproduce the *first concrete error* from that nested build. Avoid ambiguous reruns (e.g., running only the top-level reactor with different goals/profiles) that diverge from what the Invoker executed.

Do not assume versions declared in the parent module automatically govern an
Invoker integration-test POM. An integration-test POM copied or synchronized
separately can become stale.



## Toolchain selection and validation

Before changing source or dependencies, make the local environment *match CI* (Maven executable, JVM args, and JDK selection). Record what you used so the failure is reproducible.

1) **Use the Maven Wrapper when present (required)**
- If `./mvnw` exists, use it for *all* reproduction commands. Do not substitute system `mvn` unless CI explicitly does.
- Read Maven/JVM configuration that CI will also apply:
  ```bash
  ls -la .mvn || true
  [ -f .mvn/jvm.config ] && cat .mvn/jvm.config
  [ -f .mvn/maven.config ] && cat .mvn/maven.config
  ./mvnw -version
  ```
- If there is no wrapper, then use system Maven and record it:
  ```bash
  mvn -version
  ```

2) **Verify JDK selection the way the build enforces it**
- Capture the active JDK:
  ```bash
  echo "$JAVA_HOME"
  java -version
  ```
- If toolchains are used/required, align them before editing code/dependencies:
  - Inspect for `maven-toolchains-plugin` usage and/or `~/.m2/toolchains.xml` requirements.
  - Also check `maven-enforcer-plugin` rules (e.g., `requireJavaVersion`, `requireMavenVersion`) and `maven-compiler-plugin` configuration (`release` / `source` / `target`).
  - Prefer satisfying these constraints (correct JDK/toolchain) over changing source to “fit” the wrong JDK.

3) **Preserve CI profiles/properties/repositories when reproducing**
- Re-run with the same profiles (`-P...`) and properties (`-D...`) that CI uses. A build that passes without CI flags can still fail in the pipeline.
- When in doubt, start from the exact CI Maven command line and only add diagnostics (`-e`, then `-X`) after you can reproduce the failure.
## Missing library classes usually indicate dependency-version drift

For a compiler error such as:

```text
cannot find symbol: class MoreObjects
location: package com.google.common.base
```

first ask which Guava version the failing nested build actually selected.
`MoreObjects` is an API-version signal: a stale/transitively selected Guava can
make valid test source fail even though the main reactor uses a newer Guava.

For test libraries that are designed to be version-coupled (for example
`guava` and `guava-testlib`), prefer an explicit, synchronized dependency set.
Do not "fix" valid source by rewriting it to avoid the missing API unless the
source itself is demonstrated to be wrong.

## Repository-specific checkpoint: AutoValue functional integration test

In this Google Auto snapshot, the historical CI failure is inside the Maven
Invoker build rooted at:

```text
value/src/it/functional/pom.xml
```

Synchronize this functional-test POM as one coherent dependency repair:

- `com.google.code.findbugs:jsr305` -> `3.0.0` (`provided`);
- `junit:junit` -> `4.12` (`test`);
- add a direct `com.google.guava:guava:19.0` test dependency;
- `com.google.guava:guava-testlib` -> `19.0` (`test`);
- `com.google.truth:truth` -> `0.28` (`test`).

## Build-repair artifact contract

This benchmark requires both a diagnosis artifact and an applicable patch.
Before finishing:

1. Write `/home/travis/build/failed/failed_reasons.txt` with the reproduced
   target environment, the exact failing nested POM, the first real error, and
   the dependency-drift root cause.
2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/google/auto/patch_1.diff` (or the repository path
   given by the task) containing the intended source/configuration change.
3. Apply that patch to the failed repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only
   the patch artifact—was changed.
## Minimal diagnostic sequence

### Command conventions (CI-aligned)

- **Start from the exact CI Maven command** (same goals/phases, profiles, and `-D` properties). Avoid broad substitutes like “just run `mvn test`” if CI runs `verify` with profiles.
- **Prefer the Maven Wrapper** when available:
  - Use `./mvnw ...` at the repo root.
  - Inside Maven Invoker nested projects, use the wrapper only if that nested project contains its own `mvnw`; otherwise use `mvn` but keep the *same Java/toolchain*.
- Add diagnostics only after reproducing:
  - first add `-e -DtrimStackTrace=false`
  - then add `-X` if needed

### Reactor reproduction template

```bash
cd /home/travis/build/failed/google/auto

# 1) Record toolchain
./mvnw -version
java -version

# 2) Re-run the CI-equivalent command (edit to match CI: profiles/properties/settings)
./mvnw -e -DtrimStackTrace=false clean verify

# 3) Only after reproducing, add debug logging
./mvnw -X -e -DtrimStackTrace=false clean verify

# 4) Targeted rebuild (only after the full failure is understood)
./mvnw -pl <module> -am -e test
```

### Maven Invoker IT reproduction template (nested build)

1) **Find the first concrete error in the nested build log** (do not stop at the outer “Invoker failed” summary):

```bash
find . -path '*/target/it/*/build.log' -print
# Inspect the *first* failing build.log mentioned by the reactor output
sed -n '1,220p' <path-to-build.log>
```

2) **Re-run the failing nested build from its directory** using the same profiles/properties the Invoker used in CI (copy them from CI output / build.log):

```bash
cd value/src/it/functional

# Use the local Maven invocation for this nested project (often plain mvn):
mvn -e -DtrimStackTrace=false clean test
# Add -X only after the failure reproduces
mvn -X -e -DtrimStackTrace=false clean test

# Resolve what the nested project actually sees
mvn -e dependency:tree
mvn -e help:effective-pom > effective-pom.xml
```

### Skip flags: use precisely

- `-DskipTests` skips unit tests (Surefire) but may still run other checks.
- `-Dinvoker.skip=true` (or the plugin-specific property configured in the POM) skips Invoker ITs.
- Do **not** blanket-skip tests/ITs to “make CI green”; only use skip flags to isolate the phase while you work toward fixing the *first concrete error*.

## General Maven lifecycle reminders

- In multi-module projects, use the reactor summary to identify the first
  genuinely failing module, then inspect that module's own integration steps.

- For Maven Invoker integration tests, inspect the generated `build.log` under `target/it/**` before editing project code. The outer reactor failure is often only a wrapper around a nested dependency-resolution or compiler error.


- When reproducing, copy the Maven command line (goals, `-P` profiles, `-D` properties, `-s` settings, and any `-Dmaven.repo.local`) from CI/build logs and rerun it verbatim. Only then add `-e` / `-X`.
- Prefer wrapper-first conventions: `./mvnw ...` at repo root when present; do not silently switch between wrapper and system Maven because that changes Maven/JDK behavior.
- Use `dependency:tree` inside the failing nested project to confirm the selected versions of coupled libraries such as `guava` and `guava-testlib`.
- When using `-pl` and `-am`, verify that required aggregator-generated artifacts or parent POMs were installed; some legacy builds require a prior `install` phase before isolated module reproduction works correctly.
