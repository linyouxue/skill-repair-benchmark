---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle - CI Repair Workflow (Legacy + Multi-Module + Invoker ITs)

## Build-repair artifact contract (required)

This benchmark expects **(a) a diagnosis note**, **(b) at least one patch file**, and **(c) the patch applied to the repository**.

Before finishing the task:

1. **Write analysis + plan** to:
   - `/home/travis/build/failed/failed_reasons.txt`

2. **Create at least one non-empty standard unified diff** inside the failed repository directory:
   - `patch_1.diff` (and optionally `patch_2.diff`, …)
   - The repository path is provided by the task, typically:
     `/home/travis/build/failed/<repo>/<id>`

3. **Apply the patch(es)** so the *actual project files* (e.g., `pom.xml`, `src/**`) are changed, not only the patch artifact.

4. **Verify** with `git diff`/`git status` and re-run the Maven build.

**Do not hard-code** a repository name/id in commands. Always use the repository path given by the task.

### Suggested patch workflow that matches the prompt

The prompt separates “write patch” and “apply patch”. A safe way to follow that contract:

```bash
# 0) Set this from the task instructions
REPO_DIR=/home/travis/build/failed/<repo>/<id>
cd "$REPO_DIR"

# 1) Make edits (or stage them)

# 2) Export a patch artifact
git diff > patch_1.diff

# 3) Sanity-check the patch applies cleanly
git apply --check patch_1.diff

# 4) (Optional, only if you need strict step ordering)
# If you already edited files directly but want to prove the patch is what applies,
# you can reset and then apply the patch:
#   git reset --hard
#   git apply patch_1.diff
```

## Toolchain selection (Java + Maven)

Legacy Maven builds are sensitive to toolchain drift. Establish the toolchain *before* making changes.

1. **Prefer Maven Wrapper** when present:
   - If `./mvnw` exists, use `./mvnw` for all commands.
   - Otherwise, use `mvn`.

2. **Record versions** (useful for `failed_reasons.txt`):

```bash
java -version
mvn -version  # or: ./mvnw -version
```

3. **Infer required Java version from the build**:
   - Look for `maven-compiler-plugin`, `maven.compiler.release`, `maven.compiler.source/target`, or `<java.version>`.
   - Check for `maven-enforcer-plugin` rules enforcing Java/Maven versions.

4. **When the required Java level and environment disagree**:
   - Prefer fixing the project configuration/code to work with the available toolchain.
   - Avoid assumptions like “install a new JDK” unless the environment explicitly supports it.

## Failure reproduction: run the same thing CI runs

1. **Find the CI entrypoint** (common locations):
   - `.github/workflows/*.yml`, `.travis.yml`, `Jenkinsfile`, `pom.xml` profiles referenced by CI.

2. **Re-run the matching Maven goals and flags**.

Recommended baseline commands:

```bash
# Fast feedback (build without executing tests):
./mvnw -B -e -DskipTests install

# Full verification (unit + integration tests if configured):
./mvnw -B -e verify
```

Notes:
- `-DskipTests` skips *execution* but still compiles tests; `-Dmaven.test.skip=true` skips compiling tests too.
- If logs are too terse, add `-DtrimStackTrace=false` and/or rerun with `-X` after you have a minimal reproducer.

3. **Capture a minimal, actionable diagnosis** in `/home/travis/build/failed/failed_reasons.txt`:
   - the first failing module and goal (e.g., “Failed to execute goal … on project …”)
   - the root error (exception message / compilation error)
   - the exact command to reproduce
   - a small plan (what file(s) to change and why)

## Efficient iteration in multi-module reactors

Large multi-module builds benefit from narrowing scope while iterating:

```bash
# Build only one module (+ dependencies) by artifactId
./mvnw -pl :<artifactId> -am -DskipTests install

# Re-run a single test
./mvnw -Dtest=<TestClassOrPattern> test
```

Always return to the full CI command (`test`/`verify`) before declaring the fix complete.

## Maven Invoker / nested integration-test projects (common pitfall)

Some repositories run **integration tests by invoking Maven builds of nested sample projects** (often via `maven-invoker-plugin`). These projects commonly live under directories like:
- `src/it/**`, `src/it-projects/**`, `it/**`, or under `src/test/resources/**`

Key conventions:

1. **Generated copies are not the source of truth**
   - Invoker-style tests frequently copy projects to `target/it/**` (or similar) and run Maven there.
   - **Never edit `target/**`**. Edits will be overwritten on the next run.
   - Always edit the original fixture sources under `src/it/**` (or the configured directory).

2. **Fixture POMs often use filtered placeholders**
   - You may see placeholders like `@project.version@`, `${project.version}`, or `${revision}` in fixture `pom.xml` files.
   - Preserve placeholders when possible; avoid replacing them with a one-off literal version.

3. **Dependency resolution for nested projects**
   - Nested builds typically resolve the “build under test” artifacts from the **local Maven repository**.
   - If nested projects fail to resolve your project’s artifacts, ensure the main reactor has produced and installed them:

```bash
# Typical two-step reproducer
./mvnw -DskipTests install
./mvnw verify
```

4. **Modification scope**
   - Acceptable fixes may involve:
     - parent POM / plugin configuration that controls Invoker execution
     - fixture project `pom.xml` / `invoker.properties` / scripts under `src/it/**`
   - Avoid fixes that depend on changing global state outside the repo (e.g., editing `~/.m2/settings.xml`).

## Final verification checklist

Before finishing:

- [ ] `/home/travis/build/failed/failed_reasons.txt` exists and explains root cause + plan.
- [ ] `patch_1.diff` exists in the failed repo directory and is non-empty.
- [ ] `git apply --check patch_1.diff` succeeds.
- [ ] The patch is applied: `git status --porcelain` shows intended project file changes.
- [ ] The full Maven command used by CI (`test` or `verify`) succeeds.
