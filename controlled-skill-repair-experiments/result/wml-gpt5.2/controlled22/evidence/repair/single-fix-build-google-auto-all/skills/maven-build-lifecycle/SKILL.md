---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Build-repair artifact contract

This benchmark requires both a diagnosis artifact and one or more applicable patches.

### Workspace binding (do this first)

The repository is located at:

- `/home/travis/build/failed/<repo>/<id>`

Bind that location once and derive all artifact paths from it:

```bash
# Fill these in from the benchmark instance
REPO_SLUG="<repo>"   # e.g. org/name
RUN_ID="<id>"        # e.g. 123

REPO_DIR="/home/travis/build/failed/${REPO_SLUG}/${RUN_ID}"
PATCH_1="${REPO_DIR}/patch_1.diff"
# Add more as needed: PATCH_2="${REPO_DIR}/patch_2.diff" ...

FAILED_REASONS="/home/travis/build/failed/failed_reasons.txt"
```

### Required outputs

Before finishing:

1. Write your analysis/plan to:
   - `/home/travis/build/failed/failed_reasons.txt`
2. Create at least one non-empty standard unified diff at:
   - `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`
3. Apply that patch (or patches) to the repository.
4. Check `git diff`/`git status` and ensure the intended project file—not only
   the patch artifact—was changed.

## Minimal diagnostic sequence

```bash
cd "${REPO_DIR}"

# Record toolchain (helps explain CI-only failures)
java -version
mvn -v || true

# Prefer Maven Wrapper if present (matches repo-pinned Maven version)
if [ -x ./mvnw ]; then
  MVN=./mvnw
else
  MVN=mvn
fi

# Fast, high-signal reproduction attempts (pick the one that matches the failure)
# 1) Default verification (most CI jobs)
"${MVN}" -e -DtrimStackTrace=false clean verify

# 2) If you need more detail
# "${MVN}" -X -e -DtrimStackTrace=false clean verify

# 3) If tests are too slow/noisy and the failure is compilation/packaging
# "${MVN}" -e -DskipTests clean verify

# 4) If the project uses profiles in CI, mirror them explicitly
# "${MVN}" -e -Pci clean verify
```

## Toolchain selection & failure reproduction protocol

1. **Choose Maven executable**
   - Use `./mvnw` when available and executable. This best matches the project’s
     intended Maven version and avoids “works locally, fails in CI” due to Maven
     version drift.
   - Otherwise use system `mvn`.

2. **Capture versions early**
   - Always record `java -version` and `mvn -v` in your notes. Many failures are
     caused by Java release level (`--release`, `maven-compiler-plugin`) or
     enforcer rules.

3. **Use a canonical reproduce command**
   - Default: `clean verify` (covers compilation + unit tests + integration tests
     when configured).
   - Add `-e` for stack traces; add `-X` only when needed.
   - Avoid `-DskipTests` unless you have evidence the failure is outside tests.

4. **Mirror CI flags/profiles**
   - Check for CI scripts/config (e.g., `.travis.yml`, GitHub Actions, Jenkinsfile)
     and reproduce with the same profiles and properties (`-P...`, `-D...`).

5. **Multi-module targeting (when narrowing scope)**
   - Use `-pl :module -am` to focus on a failing module while still building
     required dependencies.

## Invoker & nested projects (integration-test fixtures)

Some Maven builds run *nested* Maven projects as fixtures (common in plugin
projects) via `maven-invoker-plugin` or integration-test directories.

### How to detect

- Look for `maven-invoker-plugin` in `pom.xml`.
- Common fixture locations:
  - `src/it/**`
  - `src/it/projects/**`
  - `src/test/resources/**` containing embedded `pom.xml`
- Look for `invoker.properties`, `invoker.xml`, or `verify.groovy`.

### Reproducing invoker runs

- Invoker executions are usually bound to `integration-test`/`verify`.
- Prefer running the same lifecycle phase the build uses:
  - `"${MVN}" -e clean verify`
- If you need to isolate invoker-only behavior, run the module that configures it:
  - `"${MVN}" -e -pl :<plugin-module> -am verify`

### Dependency resolution boundaries for nested projects

- Nested fixture builds often rely on artifacts produced by the outer build.
  If a fixture fails to resolve dependencies:
  - Ensure the outer build installs required artifacts first (e.g., `install`),
    or that the invoker is configured to use the reactor/local repo as intended.
  - Check invoker settings such as local repository location and whether it uses
    `-Dmaven.repo.local=...`.

### Modification scope rules (keep changes minimal and durable)

- Prefer fixing the **real build** (parent POM, plugin configuration, dependency
  management) rather than editing many fixture projects.
- Only edit fixture `pom.xml`/files when:
  - The failure is demonstrably inside the fixture itself, and
  - The change is minimal and does not invalidate the fixture’s purpose.
- Avoid broad refactors across many `src/it/**` projects; treat them as test data.

## General Maven lifecycle reminders
n