---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — CI Repair Workflow

## Toolchain selection (Maven + JDK)

1. Prefer the Maven Wrapper (`./mvnw`) if present; it pins a Maven version closer to what CI used.
2. Otherwise use system Maven (`mvn`).
3. Record the toolchain in your diagnosis notes:
   - `./mvnw -v` or `mvn -v`
   - `java -version`

If you see errors like **"invalid target release"**, **"unsupported major.minor version"**, or bytecode/version mismatches, align the Java version with what the project/CI expects (check the CI config and `maven-compiler-plugin` configuration).

## Reproduce the failure the same way CI does

- Start from the repository root path provided by the task (commonly `/home/travis/build/failed/<repo>/<id>`).
- Mirror CI goals/profiles first; then narrow down once you know the first failing module.

Suggested baseline reproduction command (use wrapper if present, include stack traces):

```bash
REPO=/home/travis/build/failed/<repo>/<id>
cd "$REPO"
MVN=./mvnw; [ -x "$MVN" ] || MVN=mvn

$MVN -e -DtrimStackTrace=false clean verify
```

Once you have the first failing module, rerun more narrowly to iterate faster:

```bash
$MVN -e -DtrimStackTrace=false -pl :<artifactId> -am test
```

## Maven Invoker failures: debug the nested project, not just the reactor

`maven-invoker-plugin` can launch independent Maven builds from integration test projects such as `src/it/*/pom.xml`. Those nested builds have their own dependency mediation and can fail even when the parent module's normal unit tests pass.

If Maven reports output similar to:

```text
The following builds failed:
*  <it-project>/pom.xml
```

then:

1. Locate the exact integration-test POM named by the Invoker (often under `.../src/it/<name>/pom.xml`).
2. Read the corresponding Invoker `build.log` and/or `invoker-reports` output (commonly under `target/it/...`).
3. Identify the *first concrete compiler/test error* inside that nested build.
4. Inspect the nested POM's direct dependencies and resolved versions.
   - Run `mvn help:effective-pom` and `mvn dependency:tree` inside the nested build directory if needed.
5. Repair the nested dependency/configuration drift instead of broad-editing unrelated top-level modules.

Do not assume versions declared in the parent reactor automatically govern an Invoker integration-test POM. Some IT POMs are copied or maintained separately and can become stale.

## Dependency-drift signals in nested builds

Common symptoms that point to nested-build dependency/version drift:

- "cannot find symbol" for a class/method that exists in newer versions of a library
- test-only artifacts that are designed to be version-coupled (e.g., `<lib>` and `<lib>-testlib`) resolving to different versions
- `NoSuchMethodError` / `ClassNotFoundException` during tests even though the main reactor compiles

Prefer aligning versions/configuration in the nested POM (or via a BOM/import that the nested POM actually inherits) rather than rewriting valid source code to avoid an API.

## Build-repair artifact contract (SkillHone tasks)

This task family requires both a diagnosis artifact and one or more patch artifacts.

Before finishing:

1. Write `/home/travis/build/failed/failed_reasons.txt` with:
   - the toolchain used (JDK + Maven/wrapper),
   - the exact failing command and module or nested IT project path,
   - the first real error, and
   - the root cause you believe fixes it.
2. Create at least one non-empty standard unified diff:
   - `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (and `patch_2.diff`, … if needed).
3. Apply your patch file(s) to the repository (e.g., with `git apply`) and verify the intended project files changed.

## Minimal diagnostic sequence

```bash
REPO=/home/travis/build/failed/<repo>/<id>
cd "$REPO"
MVN=./mvnw; [ -x "$MVN" ] || MVN=mvn

$MVN -v
$MVN -e -DtrimStackTrace=false clean verify

# If Invoker is involved, inspect common log locations:
find . \( -path "*/target/it/*/build.log" -o -path "*/target/invoker-reports/*" \) -print
```

## General Maven lifecycle reminders

- In multi-module projects, use the reactor summary to identify the first genuinely failing module, then inspect that module's own integration steps.
