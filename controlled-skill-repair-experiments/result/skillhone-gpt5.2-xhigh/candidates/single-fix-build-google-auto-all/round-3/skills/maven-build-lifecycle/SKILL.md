---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — CI Repair Workflow

Use this skill to **reproduce** a failing Maven build locally, **isolate** the failing module/phase, and **apply** a minimal fix while producing the artifacts required by the task prompt.

## 0) Benchmark contract: repo location + required artifacts (do this first)

Many tasks in this benchmark require both a diagnosis note and one or more patch artifacts at **specific absolute paths**. The grader typically checks these paths exactly — don’t wait until the end to create them.

Common prompt conventions:

- Repository directory: `/home/travis/build/failed/<repo>/<id>`
- Diagnosis note: `/home/travis/build/failed/failed_reasons.txt`
- Patch diffs: `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (and `patch_2.diff`, …)

### Set paths from the prompt (keep them parameterized)

Do **not** hard-code a specific `<repo>` or `<id>` value in the skill. Take the repository path from the prompt and then set variables from it.

Two safe patterns:

```bash
# Pattern A: you already cd'ed into the repo mentioned in the prompt
REPO_DIR="$(pwd)"

# Pattern B: copy the path from the prompt, then cd
REPO_DIR="/home/travis/build/failed/<repo>/<id>"  # copy exactly from the prompt
cd "$REPO_DIR"
```

```bash
FAILED_ROOT="/home/travis/build/failed"
DIAG_FILE="$FAILED_ROOT/failed_reasons.txt"
PATCH_DIR="$REPO_DIR"
PATCH_FILE="$PATCH_DIR/patch_1.diff"
```

### Always create/update the diagnosis note

Create the note as soon as you can reproduce the failure (or as soon as you discover you can’t reproduce it yet). Keep it updated as you narrow down the root cause.

```bash
mkdir -p "$(dirname "$DIAG_FILE")"
cat > "$DIAG_FILE" <<'EOF'
Build command used:
- ...

Observed failure (key error lines):
- ...

Likely cause:
- ...

Plan:
1) ...
2) ...

Progress / what I tried:
- ...
EOF
```

### Produce a **non-empty unified diff** patch at the required path

After you make the minimal repository changes, generate a patch file. Prefer `git diff` when a `.git/` directory is present.

```bash
mkdir -p "$PATCH_DIR"

# If you created any new files, make them appear in git diff:
#   git add -N path/to/new-file

git diff > "$PATCH_FILE"

# The patch must be non-empty
test -s "$PATCH_FILE"
```

#### If the repository is not a Git checkout (no `.git/`)

Some benchmark checkouts may not include `.git/`. In that case, create a temporary local Git history **only** to generate a patch:

```bash
if [ ! -d .git ]; then
  git init
  git config user.email "local@example.invalid"
  git config user.name "local"
  git add -A
  git commit -m "baseline"
fi

git diff > "$PATCH_FILE"
test -s "$PATCH_FILE"
```

Before finishing, confirm:

- `test -s /home/travis/build/failed/failed_reasons.txt`
- `test -s /home/travis/build/failed/<repo>/<id>/patch_1.diff`

## 1) Choose the correct Maven command and Java toolchain

### Prefer the Maven Wrapper when present

From the repository root, check for a wrapper:

- `./mvnw` (Unix)
- `.mvn/wrapper/maven-wrapper.properties`

If the wrapper exists, use it (it pins a Maven distribution compatible with the project).

```bash
# Ensure it is executable when checked out without +x
[ -f ./mvnw ] && chmod +x ./mvnw || true

if [ -x "./mvnw" ]; then
  MVN="./mvnw"
else
  MVN="mvn"
fi

$MVN -v
```

Use `$MVN …` consistently for all commands in this task.

### Confirm the Java version requirements

Build failures often come from a **Java/Maven mismatch** rather than code.

Checklist:

- Look for `maven-compiler-plugin` configuration (`<source>`, `<target>`, `<release>`), `maven-toolchains-plugin`, or `maven-enforcer-plugin` rules like `requireJavaVersion`.
- Confirm the JDK Maven is using via `$MVN -v`.
- Avoid “fixing” by globally changing toolchains unless the project explicitly requires it.

## 2) Reproduce the failure (baseline commands)

Start with a command that matches Maven’s standard lifecycle and produces useful logs.

```bash
# Fast signal: compile + unit tests
$MVN -B -e test

# Full build signal (includes integration-test/verify where configured)
$MVN -B -e verify
```

Conventions:

- Use `-B` (batch) to reduce interactive noise.
- Add `-e` to include exception stack traces.
- Only use `-X` (debug) after you’ve narrowed the failing area.

If the project is multi-module, run from the **root aggregator POM** (the one listing `<modules>`).

## 3) Isolate the failing module, phase, or test

### Identify the failing module

When Maven prints “Reactor Summary” it shows which module failed.

Common narrowing patterns:

```bash
# Build only one module and whatever it depends on
$MVN -B -e -pl :<artifactId> -am test

# Resume from a failing module
$MVN -B -e -rf :<artifactId> test
```

### Separate compilation from tests

To decide whether you’re dealing with compilation vs tests vs packaging:

```bash
# Compilation only
$MVN -B -e -DskipTests compile

# Run a single test (Surefire)
$MVN -B -e -Dtest=<TestClass> test
```

Use skipping flags only as **diagnostic tools** unless the prompt explicitly allows skipping.

## 4) Special case: Maven Invoker / nested test projects

Legacy plugin builds frequently use `maven-invoker-plugin` to run integration tests that build **nested sample projects**.

### How to recognize it

Look for `maven-invoker-plugin` in the root POM (or a plugin module POM) and directories such as:

- `src/it/...`
- `src/it/projects/...`
- `src/it/<test-name>/pom.xml`

Invoker will typically copy templates into a generated directory under `target/` (for example `target/it` or `target/invoker`).

### Key rule: edit the *checked-in* templates, not generated copies

- Do **not** patch generated copies under `target/`.
- Patch the checked-in sources under `src/it/` (or the invoker `cloneProjectsTo` directory configured in the POM).

### Dependency resolution in nested projects

A nested project is usually built by a **separate Maven process**, which means it may not automatically “see” the current reactor unless the build is configured to make artifacts available.

If a nested project fails because it can’t resolve dependencies/plugins (common symptoms: “Could not find artifact …”, missing SNAPSHOTs, missing plugin prefix):

- Determine whether it should resolve artifacts from the **current build output** (reactor) or from a local/remote repository.
- Prefer fixes that keep builds reproducible:
  - make nested POMs inherit/align versions via properties
  - avoid adding ad-hoc remote repositories unless the build already depends on them
- Keep the scope of changes minimal:
  - If only integration test templates are broken, change `src/it/**`.
  - If the main build must publish artifacts for invoker to consume, prefer a lifecycle/config fix that ensures the needed artifacts are available before invoker runs (for example via install-to-local-repo behavior configured by the build).

## 5) Apply a minimal fix and validate

After implementing a change:

1. Re-run the smallest command that demonstrates the fix (often `-pl … -am test`).
2. Re-run the broader lifecycle phase that originally failed (`test` or `verify`).
3. Re-generate the patch file at the required location:
   `git diff > /home/travis/build/failed/<repo>/<id>/patch_1.diff`
4. Ensure no unintended files changed (avoid committing `target/`, downloaded artifacts, IDE files).

If the failure is build-configuration related, consider reviewing:

- `dependencyManagement` alignment (see skill: `maven-dependency-management`)
- plugin versions/config (`maven-plugin-configuration`)
- enforcer rules and toolchains

## Troubleshooting quick hits

- **Maven can’t find a parent POM / wrong module directory**: ensure you’re in the correct root and not a submodule.
- **Wrong Maven selected**: if a wrapper exists, ensure you’re using `./mvnw` consistently.
- **Tests are flaky or environment-dependent**: isolate with `-Dtest=...` and confirm whether the failure is deterministic.
- **Invoker failures**: inspect invoker reports/logs under `target/` (the exact directory is configurable by the plugin) and ensure you’re editing templates, not copied projects.
