---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Scope and boundary

This Skill covers **how to reproduce a Maven build failure, capture the required benchmark artifacts, and apply a minimal fix**.

It does **not** prescribe a specific repository name/path. Always derive the repo root from the task-provided location:

- Repo root: `/home/travis/build/failed/<repo>/<id>`
- Diagnosis notes file (global, outside repo): `/home/travis/build/failed/failed_reasons.txt`
- Patch files (inside repo): `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`

## Build-repair artifact contract (benchmark requirements)

Before finishing the run, ensure **all** of the following are true:

1. **Diagnosis artifact exists**: write analysis + plan to:
   - `/home/travis/build/failed/failed_reasons.txt`

2. **At least one non-empty patch artifact exists**: create at least one standard unified diff:
   - `/home/travis/build/failed/<repo>/<id>/patch_1.diff`

3. **Patch is applied to the repository**: the actual project files must be modified (not only the patch file).

4. **Verification**:
   - `git diff` shows the intended changes
   - `git status` shows modified files as expected
   - A Maven build command that matches CI intent succeeds (see “Reproduce and validate” below)

## Toolchain selection (Maven wrapper vs system Maven)

Prefer the project’s Maven Wrapper when present:

- If `./mvnw` exists: use `./mvnw` (and `./mvnw -v` to confirm)
- Otherwise: use `mvn` (and `mvn -v` to confirm)

Record the chosen toolchain and versions in `failed_reasons.txt`.

## Minimal diagnostic sequence

> Replace `<repo>` and `<id>` with the actual directory names from the task environment.

```bash
REPO_ROOT="/home/travis/build/failed/<repo>/<id>"
cd "$REPO_ROOT"

# Confirm structure
ls

# Confirm toolchain
if [ -x ./mvnw ]; then ./mvnw -v; else mvn -v; fi

# Capture baseline state
git status --porcelain
```

## Reproduce and validate (build command conventions)

### 1) Start with the least-surprising Maven command

Use a command that is broadly compatible with multi-module builds:

```bash
# choose one of these depending on wrapper availability
./mvnw -e -DskipTests=false test
# or
mvn -e -DskipTests=false test
```

If the CI likely runs a full install/verify, prefer:

```bash
./mvnw -e verify
# or
mvn -e verify
```

### 2) When reproduction is flaky or logs are insufficient

Re-run with more diagnostics:

```bash
./mvnw -e -X verify
# or
mvn -e -X verify
```

Also consider forcing updates if dependency resolution looks stale:

```bash
./mvnw -U -e verify
# or
mvn -U -e verify
```

### 3) Multi-module targeting (avoid over-building)

If the failure is isolated to a module, reproduce with `-pl` and `-am`:

```bash
./mvnw -e -pl :<artifactId> -am test
```

Use this to speed iteration, but **final validation** should match the likely CI entrypoint (often `verify` at the root).

## Nested test projects / Maven Invoker integration tests

Some repositories include **nested Maven projects** used only for integration testing (commonly via `maven-invoker-plugin`). These often live under directories like:

- `src/it/**`
- `src/test/resources/**` containing embedded `pom.xml`
- `it/**`, `integration-tests/**`, `examples/**` (varies by project)

### How to detect invoker/nested-project failures

1. Search for invoker usage:

```bash
grep -R "maven-invoker-plugin" -n pom.xml **/pom.xml 2>/dev/null || true
```

2. If the failing log references an integration test project path (e.g., `.../src/it/<case>/pom.xml`), treat that nested project as the **immediate reproduction target**.

### Modification scope rules (avoid overfitting / over-editing)

- Prefer fixing the **root build** (parent POM, shared plugin/dependency management) when the issue affects normal modules.
- Prefer fixing a **nested invoker project** only when:
  - the failure occurs exclusively in that invoker case, and
  - changing the root would be broader than necessary.
- Avoid “global” dependency version bumps unless the failure clearly requires it.
- When editing nested projects, keep changes minimal and local to the failing case directory.

Record in `failed_reasons.txt` **why** the chosen modification scope is correct (root vs module vs nested invoker project).

## Writing `failed_reasons.txt` (required content checklist)

Write concise notes that enable Step 2 without re-discovery:

- Repo root path used
- Maven toolchain used (`./mvnw` vs `mvn`) and versions
- Exact reproduction command(s)
- The first failing error (copy the key stack trace / compiler error / plugin failure line)
- Classification: code vs build config vs dependency resolution
- Plan: minimal set of files to change and why (including whether nested/invoker projects are involved)

## Patch workflow (diff-first, then apply)

1. Make edits in the working tree.
2. Create a unified diff file inside the repo:

```bash
cd "/home/travis/build/failed/<repo>/<id>"
git diff > patch_1.diff
test -s patch_1.diff  # ensure non-empty
```

3. Apply changes are already in the working tree if you edited files directly; if you generated the diff elsewhere, apply it:

```bash
git apply patch_1.diff
```

4. Verify:

```bash
git diff
git status
```

## General Maven lifecycle reminders

- `test` runs unit tests (Surefire); `verify` runs checks and integration tests (often Failsafe/Invoker).
- Many CI failures are caused by:
  - compiler source/target mismatch
  - missing plugin versions in older POMs
  - dependency convergence / upper-bound issues
  - invoker integration test fixture POMs drifting from parent expectations

When in doubt, reproduce at the **root** first, then narrow to the failing module or invoker case.
