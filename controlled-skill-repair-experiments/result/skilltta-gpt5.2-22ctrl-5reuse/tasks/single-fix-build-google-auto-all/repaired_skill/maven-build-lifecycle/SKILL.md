---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — CI Repair Workflow

## Build-repair artifact contract (benchmark workflow)

This benchmark expects **both** a diagnosis artifact and one or more applicable patches, produced in a **specific** order.

1. **Step 1 (analyze):** write analysis + plan to:
   - `/home/travis/build/failed/failed_reasons.txt`
2. **Step 2 (propose changes as diffs):** create at least one **non-empty** unified diff patch file under the repository directory:
   - `/home/travis/build/failed/<repo>/<id>/patch_1.diff`
   - (optional additional patches) `/home/travis/build/failed/<repo>/<id>/patch_2.diff`, ...
3. **Step 3 (apply):** apply patches to the repository (e.g., `git apply patch_1.diff`) and verify the build.
4. Confirm the repo changed (not only the patch artifact):
   - `git status` / `git diff`

**Do not hardcode a specific repo path**. Always use the repository location provided by the task prompt: `/home/travis/build/failed/<repo>/<id>`.

## Toolchain selection + entering the repository

Use this to select Maven vs other build tools and capture basic environment info.

```bash
cd /home/travis/build/failed/<repo>/<id>

# Identify toolchain (prefer evidence over assumptions)
ls
# Maven indicator: pom.xml
# Maven wrapper indicator: mvnw / .mvn/
# Gradle indicator: gradlew / build.gradle / build.gradle.kts

# Prefer project wrappers when present (they pin tool versions and flags)
if [ -x ./mvnw ]; then
  MVN=./mvnw
else
  MVN=mvn
fi

# Capture environment (helpful for toolchain mismatch issues)
java -version
$MVN -version
```

Recommended for CI-like output (when iterating or when logs are noisy):

- Add `-B` (batch mode) and `-ntp` (no transfer progress): `"$MVN -B -ntp ..."`

If the repository does **not** appear to be Maven-based (no `pom.xml` at the intended root), stop and reassess the correct root directory or toolchain.

## Minimal diagnostic sequence (reproduce with actionable logs)

### 1) Find the correct Maven reactor root

Many repositories contain multiple `pom.xml` files (multi-module builds, examples, integration-test fixtures). Identify the **reactor root** before running Maven.

```bash
# Quick inventory (adjust maxdepth if needed)
find . -maxdepth 4 -name pom.xml -print

# Common hint: the reactor root pom often has <packaging>pom</packaging> and a <modules> section.
```

From the candidate root directory, sanity-check what Maven thinks the project is:

```bash
$MVN -q -DskipTests help:evaluate -Dexpression=project.groupId -DforceStdout
$MVN -q -DskipTests help:evaluate -Dexpression=project.artifactId -DforceStdout
$MVN -q -DskipTests help:evaluate -Dexpression=project.version -DforceStdout
```

### 2) Reproduce the failure

Start with a deterministic command that yields useful error context:

```bash
# Typical baseline reproduction
$MVN -e -DtrimStackTrace=false test
```

If you need deeper Maven/plugin resolution details:

```bash
$MVN -X test
```

If the failure is dependency-resolution related (stale/partial local cache, snapshots, missing artifacts):

```bash
$MVN -e -U -DtrimStackTrace=false test
```

If you need a fast signal while iterating on compilation/config without running tests:

```bash
$MVN -e -DskipTests package
```

### 3) Narrow scope in multi-module builds

When only one module fails, reduce iteration time using:

```bash
# Build a single module and required dependencies
$MVN -e -pl :<artifactId> -am test
```

Use this only after you have confirmed the failing module from the full reactor output.

## Nested projects, integration tests, and safe modification scope

### Recognizing nested Maven projects

Repositories often include nested Maven projects that are **not** part of the main reactor, such as:

- Maven Invoker / integration-test fixtures: `src/it/**`, `it/**`, `integration-tests/**`
- Sample projects: `examples/**`, `samples/**`

These nested projects may be built indirectly by plugins (not via `<modules>`), or may exist purely as fixtures for tests.

### Dependency resolution in nested/Invoker-built fixtures

When Maven Invoker (or similar) runs, failures may reference paths like:

- `.../target/it/<fixture-name>/...`
- `.../src/it/<fixture-name>/...`

Guidance:

- Prefer fixing the **main build** (parent/root POM, plugin configuration, dependency management) when the fixture is meant to validate real user behavior.
- Only edit a nested fixture `pom.xml` when:
  1) the test explicitly asserts that that fixture must build as-is, and
  2) the failure is truly contained in the fixture and cannot be addressed by the plugin/test harness configuration.

### Safe modification scope rules (to avoid changing the wrong project)

1. Default: modify files under the main reactor (`<modules>` tree) first.
2. Avoid modifying `examples/`, `samples/`, `src/it/`, `it/`, `integration-tests/` unless you have evidence they are built/required by CI.
3. If CI builds a nested project via a plugin, prefer adjusting:
   - plugin versions/configuration in the main POM, or
   - shared dependency management/version alignment,
   before editing fixture projects.

## General Maven lifecycle reminders (what runs when)

- `validate` → project sanity checks
- `compile` → compile main sources
- `test` → run unit tests (usually **Surefire**)
- `package` → create JAR/WAR/etc.
- `verify` → run checks/integration tests (often **Failsafe** or Invoker-based checks)
- `install` → install artifacts to local repository

Common debugging patterns:

- If unit tests fail: focus on Surefire config and `src/test/java`.
- If integration tests fail: look for Failsafe/Invoker config and `verify` phase bindings.
- If compilation fails with Java version errors (e.g., “source option X is no longer supported”): verify `maven-compiler-plugin` and the JDK in use.

## Output discipline (tie commands back to benchmark artifacts)

While reproducing and fixing:

- Record in `/home/travis/build/failed/failed_reasons.txt`:
  - the exact command(s) run (including whether you used `./mvnw` vs `mvn`)
  - the chosen reactor root and failing module
  - the first causal error excerpt
  - your minimal fix plan and which files will change
- Produce patch diffs at `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`.
- Apply patches and re-run the same Maven command that reproduced the failure.
