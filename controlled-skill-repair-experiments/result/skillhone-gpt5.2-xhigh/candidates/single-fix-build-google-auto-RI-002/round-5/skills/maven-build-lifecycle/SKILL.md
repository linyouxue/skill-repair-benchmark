---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Start here (first 60 seconds): create required benchmark artifacts

Many build-repair benchmarks are graded on **artifacts**, not just a green build.
If the task prompt requests them, create the required files immediately (even as
placeholders) and keep them updated while you work.

Typical required paths (follow the task’s *exact* paths):

- Diagnosis note: `/home/travis/build/failed/failed_reasons.txt`
- Patch diffs: `/home/travis/build/failed/<repo>/<id>/patch_1.diff`,
  `/home/travis/build/failed/<repo>/<id>/patch_2.diff`, …

Practical snippet (safe to run early):

```bash
# First, `cd` to the repo path given in the task prompt, e.g.:
#   cd /home/travis/build/failed/<repo>/<id>

FAILED_BASE=/home/travis/build/failed
NOTE="$FAILED_BASE/failed_reasons.txt"

# From anywhere inside the repo, resolve the repo root reliably.
REPO_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PATCH_1="$REPO_DIR/patch_1.diff"

mkdir -p "$FAILED_BASE"
: > "$NOTE"
: > "$PATCH_1"   # placeholder; regenerate to a NON-empty unified diff before finishing
```

After you make changes, (re)generate the diff artifact using an **absolute** path
so it lands where the evaluator expects:

```bash
cd "$REPO_DIR"

# Capture edits to tracked files relative to the current checked-out commit.
# If you added new files, stage them and use `--cached` instead.
git diff --no-color HEAD > "$PATCH_1"

test -s "$PATCH_1"
git apply --check "$PATCH_1"
```

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

Then run the **exact** CI build command. If CI uses a non-default reactor POM
(`-f ...`) or extra properties, include them.

Example pattern (do **not** copy blindly; take the real command from CI):

```bash
mvn -B -U -f <reactor-pom>.xml verify --fail-at-end
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

## Build-repair artifact contract

This benchmark requires **both** a diagnosis note and at least one applicable patch.
Create the required files early (even as placeholders) and update them as you learn more.

### Diagnosis note (`failed_reasons.txt`)

- Path is dictated by the task (often `/home/travis/build/failed/failed_reasons.txt`).
- Write: the exact repro command, the first failing error, the suspected root cause,
  and a concrete fix plan.

Practical snippet:

```bash
# Create/update the required note early (safe if it already exists).
mkdir -p /home/travis/build/failed
cat > /home/travis/build/failed/failed_reasons.txt <<'EOF'
Reproduction
- CI command: (paste exact command)
- Failure: (first error line + module / IT project)

Hypothesis
- (why it fails)

Plan
1) (what to change, where)
2) (how to validate)
EOF
```

### Patch artifact (`patch_*.diff`)

- Patch file path is dictated by the task (often inside the failed repo directory, e.g.
  `/home/travis/build/failed/<repo>/<id>/patch_1.diff`).
- Do **not** rely on “I changed files” — the benchmark checks for a **non-empty** unified
  diff file.

Practical snippet (run from the failed repo root):

```bash
# Ensure the patch file exists where the evaluator expects it.
# For these benchmarks, that is often *in the repo root* as `patch_1.diff`.
: > patch_1.diff

# After editing files, (re)generate the diff artifact.
# Using HEAD captures both staged and unstaged edits to tracked files.
git diff --no-color HEAD > patch_1.diff

# If your fix adds new files, stage them first so they appear in the diff artifact:
#   git add path/to/newfile
#   git diff --no-color --cached > patch_1.diff

# Sanity checks
test -s patch_1.diff
git apply --check patch_1.diff
```

If the task instead requires an *absolute* patch path like
`/home/travis/build/failed/<repo>/<id>/patch_1.diff`, write to that path
explicitly:

```bash
REPO_DIR="$(git rev-parse --show-toplevel)"
PATCH_1="$REPO_DIR/patch_1.diff"

git diff --no-color HEAD > "$PATCH_1"
```

### Finish checklist

1. Reproduce the failure under the declared CI JDK/toolchain.
2. Update `failed_reasons.txt` with the real root cause and plan.
3. Produce at least one non-empty unified diff (`patch_1.diff`, `patch_2.diff`, …).
4. Ensure the patch is actually applied to the repository (not only saved as a diff file).
5. Re-run the exact CI command; do not stop at `mvn test` if CI uses `verify`.
6. Do not finish until the full reactor succeeds, including Maven Invoker integration tests.

## Minimal diagnostic sequence

```bash
cd /home/travis/build/failed/<repo>/<id>  # use the path given by the task

# 1. Establish target CI and toolchain.
sed -n '1,220p' .travis.yml

# If CI pins an older JDK and the environment provides jdk_switcher, switch
# before patching project files. Example:
source /opt/jdk_switcher/jdk_switcher.sh
jdk_switcher use openjdk7
export TRAVIS_JDK_VERSION=openjdk7

java -version
mvn -version

# 2. Reproduce the real CI command (copy it from CI config).
# Example pattern:
mvn -B -U -f <reactor-pom>.xml verify --fail-at-end
```

## Maven Invoker integration tests: nested IT projects and dependency scope

If the build runs Maven Invoker integration tests (`maven-invoker-plugin`),
Maven will execute additional Maven builds against nested “IT projects” (often
under `src/it/**`), sometimes using a dedicated local repository and/or settings
file.

Key implications:

- A dependency resolution error during an invoker run is often coming from the
  nested IT project's own `pom.xml` (plus any invoker `settings.xml`), not the
  root reactor POM.
- Invoker commonly clones IT projects into `target/**` (e.g. `target/it`,
  `target/invoker`, `target/invoker-reports`) before running Maven. Do **not**
  edit the cloned copies under `target/` — they are generated and will be
  wiped/recreated. Patch the source IT project under the configured
  `projectsDirectory` (commonly `src/it/`) instead.
- An invoker build is not “using your shell’s `mvn` command” verbatim. It may run
  Maven with its own `settings.xml`, its own local repository
  (`-Dmaven.repo.local=...`), and additional JVM options. If the main reactor
  build needs special flags/properties to resolve artifacts (common on older JDKs,
  e.g. forcing TLSv1.2), make sure the *invoker’s* Maven invocation gets the same
  configuration (via the plugin’s `settingsFile`/`localRepositoryPath` and/or
  `mavenOpts`).

Common failure patterns (what to edit):

- **Dependency/plugin cannot be resolved in an IT build**: reproduce the failing
  nested build using the invoker’s `-s` and `-Dmaven.repo.local` values. Then:
  - if it is a *regular dependency* (`Could not find artifact ...:jar`), check
    `<repositories>` (or the invoker `settings.xml` mirrors)
  - if it is a *Maven plugin* (`Plugin ... could not be resolved`), check
    `<pluginRepositories>` (plugin repos are separate from dependency repos)
  If the artifact is expected from a remote repository, add/fix repository
  definitions in the IT project’s `pom.xml` (or the invoker `settings.xml`), not
  only in the top-level reactor.
- **IT project cannot resolve a parent or plugin built by the main reactor**
  (often shows as “Non-resolvable parent POM” / “Could not find artifact …”):
  install the required artifacts into the *same* local repository the invoker
  uses before `invoker:run` (commonly by ensuring an `install`/`invoker:install`
  step happens earlier), rather than trying to “fix” it inside `target/`.
- **HTTP→HTTPS / TLS / certificate issues** on older JDKs can surface as generic
  resolution errors. If you see protocol/handshake/certificate messages in the
  IT logs, pass the required JVM options to both the top-level build *and* the
  invoker Maven runs (for example using `MAVEN_OPTS` or the invoker plugin’s
  `mavenOpts`).

Checklist:

1. Find the invoker configuration in the reactor (`pom.xml`):
   - locate `<artifactId>maven-invoker-plugin</artifactId>`
   - note `<projectsDirectory>`, `<cloneProjectsTo>`, `<localRepositoryPath>`,
     `<settingsFile>`, `<filterPropertiesFile>`, and any `invoker.properties`
     conventions
2. When the invoker run fails, identify the failing IT project:
   - the console output and/or `target/invoker-reports/**` usually include the
     failing project directory and the Maven command it ran
   - map any `target/.../<it-project>` path back to the source directory under
     `<projectsDirectory>`
3. Reproduce the failing IT build in isolation (faster iteration):
   - run Maven from the IT project's *source* directory using the same
     goals/profiles
   - if invoker uses a dedicated local repo/settings, pass them explicitly
     (`-Dmaven.repo.local=...` and `-s ...`) so dependency resolution matches the
     invoker environment
4. Apply the fix at the correct layer:
   - missing dependency/plugin repo only in the IT project → edit that IT
     project's `pom.xml` / `settings.xml` / `invoker.properties`
   - IT projects cannot resolve artifacts built in the main reactor → ensure
     those artifacts are available to the repository the invoker run uses
     (commonly by making sure the build installs them into the invoker local repo
     before `invoker:run`)

## General Maven lifecycle reminders

- `mvn test` does not imply that `mvn verify` passes. `verify` can execute
  integration-test and Invoker steps that `test` never reaches.
- A green command run under the wrong JDK is not sufficient evidence of a
  valid CI repair.
- When diagnosing invoker failures, prefer the per-project logs under
  `target/invoker-reports/` (or the directory configured by the plugin) over
  guessing based on the top-level reactor output.
