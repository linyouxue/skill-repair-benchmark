---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle - CI Repair Workflow (Legacy + Multi-Module + Invoker ITs)

## Build-repair artifact contract (required)

This benchmark expects **(a) a diagnosis note**, **(b) at least one patch file**, and **(c) the patch applied to the repository**.

Before finishing the task (treat these as *hard requirements*, not suggestions):

1. **Write analysis + plan** to the **absolute path**:
   - `/home/travis/build/failed/failed_reasons.txt`
   - (Do not write a copy inside the repo; the checker looks for this exact path.)

2. **Create at least one non-empty standard unified diff** at the **repo root**:
   - Required file: `patch_1.diff` (and optionally `patch_2.diff`, …)
   - The repository path is provided by the task, typically:
     `/home/travis/build/failed/<repo>/<id>`
   - The expected location is:
     `/home/travis/build/failed/<repo>/<id>/patch_1.diff`

3. **Apply the patch(es)** so the *actual project files* (e.g., `pom.xml`, `src/**`) are changed, not only the patch artifact.

4. **Verify** with `git diff`/`git status` and re-run the Maven build.

**Do not hard-code** a repository name/id in commands. Always use the repository path given by the task.

Suggested variables (copy/paste and fill from the task prompt):

```bash
REPO_DIR=/home/travis/build/failed/<repo>/<id>
NOTE_FILE=/home/travis/build/failed/failed_reasons.txt
PATCH_FILE="$REPO_DIR/patch_1.diff"
mkdir -p "$(dirname "$NOTE_FILE")"
touch "$NOTE_FILE"
```

Tip: create the note file early, keep it updated while you debug, and only generate `patch_1.diff` once you have a candidate fix.

### Suggested patch workflow that satisfies “write patch” then “apply patch”

The prompt explicitly separates “write diff files” and “apply diff files”. The safest way to satisfy that contract **and** guarantee you leave behind a non-empty `patch_1.diff` is:

1) Make edits in the working tree.
2) Stage the intended changes (so new files are included).
3) Export `patch_1.diff` from the staged changes.
4) Reset back to a clean tree.
5) Apply `patch_1.diff` to produce the final working-tree changes.

```bash
# 0) Set this from the task instructions
REPO_DIR=/home/travis/build/failed/<repo>/<id>
NOTE_FILE=/home/travis/build/failed/failed_reasons.txt
PATCH_FILE="$REPO_DIR/patch_1.diff"

cd "$REPO_DIR"

# 1) Make edits in the working tree
#    (Never edit generated target/** copies; they get overwritten.)

# 2) Stage the intended changes (avoid accidentally staging the patch artifacts)
git add -A
# If patch_*.diff already exists from a previous attempt, unstage it so it doesn't
# recursively include itself:
git reset -- patch_*.diff 2>/dev/null || true

# 3) Write the patch artifact from the staged changes
#    --binary preserves renames and binary files if any.
git diff --cached --binary > "$PATCH_FILE"

# Guardrail: ensure the patch is non-empty (many graders require this)
test -s "$PATCH_FILE"

# 4) Enforce the step ordering: clean tree -> apply patch
#    NOTE: `git apply --check` will FAIL if you run it while the patch is already applied.
git reset --hard

git apply --check "$PATCH_FILE"
git apply "$PATCH_FILE"

# 5) Confirm both requirements are met
ls -la "$PATCH_FILE"
git status --porcelain
```

Why this works:
- Using `git diff --cached` ensures added/removed files are captured (plain `git diff` misses untracked files).
- Resetting before `git apply --check` avoids the common pitfall where the patch appears “invalid” simply because it is already applied.

Common gotcha: if you accidentally included `patch_1.diff` in the patch itself, the file can become empty or enormous. The `git reset -- patch_*.diff` line prevents that.

If you *don’t* want to reset (e.g., you have a passing working tree already), you can skip the reset/apply steps and just generate the patch artifact. In that case, a safe sanity-check is:

```bash
# This succeeds when the patch matches the current working tree
git apply --reverse --check "$PATCH_FILE"
```

## Toolchain selection (Java + Maven)

Legacy Maven builds are sensitive to toolchain drift. Establish the toolchain *before* making changes.

1. **Prefer Maven Wrapper** when present (it pins the Maven version), but verify it actually runs:
   - If `./mvnw` exists, `chmod +x ./mvnw` and try `./mvnw -version`.
   - If the wrapper is missing `.mvn/wrapper/**` files or fails to run, fall back to `mvn`.

   Suggested snippet (reuse everywhere below):

   ```bash
   MVN=mvn
   if [ -f ./mvnw ]; then
     chmod +x ./mvnw 2>/dev/null || true
     if ./mvnw -version >/dev/null 2>&1; then
       MVN=./mvnw
     fi
   fi
   ```

2. **Record versions** (useful for `failed_reasons.txt`):

```bash
java -version
# Choose the correct Maven entrypoint (wrapper if it is usable)
MVN=mvn
if [ -f ./mvnw ]; then
  chmod +x ./mvnw 2>/dev/null || true
  if ./mvnw -version >/dev/null 2>&1; then
    MVN=./mvnw
  fi
fi
$MVN -version
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
# Choose the correct Maven entrypoint (wrapper if it is usable)
MVN=mvn
if [ -f ./mvnw ]; then
  chmod +x ./mvnw 2>/dev/null || true
  if ./mvnw -version >/dev/null 2>&1; then
    MVN=./mvnw
  fi
fi

# Fast feedback (build without executing tests):
$MVN -B -e -DskipTests install

# Full verification (unit + integration tests if configured):
$MVN -B -e verify
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
# Choose the correct Maven entrypoint (wrapper if it is usable)
MVN=mvn
if [ -f ./mvnw ]; then
  chmod +x ./mvnw 2>/dev/null || true
  if ./mvnw -version >/dev/null 2>&1; then
    MVN=./mvnw
  fi
fi

# Build only one module (+ dependencies) by artifactId
$MVN -pl :<artifactId> -am -DskipTests install

# Re-run a single test
$MVN -Dtest=<TestClassOrPattern> test
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
# Choose the correct Maven entrypoint (wrapper if it is usable)
MVN=mvn
if [ -f ./mvnw ]; then
  chmod +x ./mvnw 2>/dev/null || true
  if ./mvnw -version >/dev/null 2>&1; then
    MVN=./mvnw
  fi
fi

# Typical two-step reproducer
$MVN -DskipTests install
$MVN verify
```

4. **Modification scope**
   - Acceptable fixes may involve:
     - parent POM / plugin configuration that controls Invoker execution
     - fixture project `pom.xml` / `invoker.properties` / scripts under `src/it/**`
   - Avoid fixes that depend on changing global state outside the repo (e.g., editing `~/.m2/settings.xml`).

## Final verification checklist

Before finishing:

- [ ] `/home/travis/build/failed/failed_reasons.txt` exists and explains root cause + plan.
- [ ] `patch_1.diff` exists at `$REPO_DIR/patch_1.diff` and is non-empty.
- [ ] `git apply --check "$REPO_DIR/patch_1.diff"` succeeds.
- [ ] The patch is applied: `git status --porcelain` shows intended project file changes.
- [ ] The full Maven command used by CI (`test` or `verify`) succeeds.
