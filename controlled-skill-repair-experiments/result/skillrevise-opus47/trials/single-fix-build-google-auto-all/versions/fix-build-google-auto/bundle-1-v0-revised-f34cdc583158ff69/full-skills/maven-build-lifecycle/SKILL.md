---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds, nested Maven Invoker IT projects, and JDK-version migration breakage.
---

# Maven Build Lifecycle - Legacy CI Repair Workflow

## Artifact contract (what the task verifier observes)

1. `/home/travis/build/failed/failed_reasons.txt` exists and contains a
   diagnosis plus a repair plan (non-empty, plain text).
2. One or more unified diff files at
   `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff` (i starting at 1),
   in `git apply` / GNU `diffutils` compatible format.
3. Each patch is actually applied to the working tree. Confirm with
   `git -C <repo>/<id> status` and `git -C <repo>/<id> diff --stat` that
   project files changed, not only the `patch_*.diff` artifacts.
4. The full reactor builds green: no module in the final Maven summary may
   read `FAILURE` or `BUILD FAILURE`. Downstream failures surfaced by an
   earlier fix must also be repaired before stopping.

## Step 0 - Discover the target repo (do not hard-code paths)

```bash
BASE=/home/travis/build/failed
REPO_DIR=$(find "$BASE" -mindepth 2 -maxdepth 2 -type d | head -n 1)
echo "$REPO_DIR"
```

- If more than one candidate exists, pick the one matching the task's
  `<repo>/<id>` pattern; otherwise fail loudly rather than guessing.
- Export `REPO_DIR` and use it for every subsequent `cd`, patch path, and
  git command. Never embed a literal project name like `google/auto`.

## Step 1 - Detect toolchain and reproduce the failure

1. Inspect the build descriptor the project actually uses:
   - Prefer `build-pom.xml` if present (common in legacy Travis configs),
     otherwise `pom.xml`.
   - Read `.travis.yml` / `.github/workflows/*` if available to recover the
     exact Maven goals, profiles, and JDK version used in CI.
2. Record the active JDK (`java -version`, `mvn -v`) and the declared
   `maven.compiler.source/target` or `maven-compiler-plugin` `<release>`.
3. Reproduce with the project-native command, e.g.
   `mvn -f <descriptor> -B -fae <goals>` (use `-fae` so every failing module
   is surfaced in one pass, not just the first).
4. Save the full log; capture every `FAILURE` entry in the Reactor Summary
   and every first `ERROR` line per module into `failed_reasons.txt`.

## Step 2 - Classify each failing module

For every failing module, tag the cause before writing a patch:

- Source/code error (symbol not found, API drift).
- Build configuration (plugin version, dependency scope, repository).
- JDK migration (JDK 9+ running a JDK 6/7/8-era build). Checklist:
  - `tools.jar` system-scope dependency - remove or guard with a
    `<profile>` activated only on `jdk=[1.6,1.9)`.
  - `javax.annotation.Generated` moved out of the JDK - add
    `javax.annotation:javax.annotation-api` (or `jakarta.annotation-api`)
    as a compile dependency, or switch generated code to
    `javax.annotation.processing.Generated`.
  - `source/target 1.6` rejected by modern `javac` - raise to the lowest
    version the project tolerates, or add `--release` / `-source -target`
    consistently.
  - Internal `sun.*` / `com.sun.*` access - add
    `--add-exports`/`--add-opens` via
    `maven-compiler-plugin` `<compilerArgs>` or `argLine`.
- Nested Maven Invoker / integration-test project (e.g. `*/src/it/*`,
  `invoker.properties`, child `pom.xml` under `src/it`):
  - These are built by `maven-invoker-plugin` against the just-installed
    artifacts; a fix in the main module often requires a mirrored change
    in the IT POM (same dependency version, same source level, same
    annotation-processor path).
  - When a fix touches a shared API, grep the whole repo for every
    `pom.xml` and `*.java` under `src/it` and patch them in parallel.

## Step 3 - Author patches

- Write each change as a standard unified diff to
  `$REPO_DIR/patch_<i>.diff`, numbered from 1. Keep patches small and
  single-purpose (one root cause each) so later iterations can add more.
- Prefer `git -C "$REPO_DIR" diff > "$REPO_DIR/patch_<i>.diff"` after
  staging edits, to guarantee `git apply` compatibility.

## Step 4 - Apply and re-verify (iterate until green)

```bash
cd "$REPO_DIR"
git apply --check patch_1.diff && git apply patch_1.diff
# repeat for each patch_i.diff in order
```

Then re-run the same reproduction command from Step 1.

Hard stop-condition (do not skip):

- Scan the Maven output: `grep -E "FAILURE|BUILD FAILURE" <log>`.
- If any match remains, treat the newly surfaced errors as the next
  Failure Ledger entry, loop back to Step 2, and add `patch_<i+1>.diff`.
- Only declare completion when the Reactor Summary lists every module as
  `SUCCESS` and the final line is `BUILD SUCCESS`.
- If a module genuinely cannot be built in this environment, document the
  reason in `failed_reasons.txt` and skip it with an explicit
  `-pl !<module>` or `<skip>true</skip>` change, not by silently ignoring
  its failure.

## Fallbacks when the planned route fails

- `mvn` missing or wrong version: try `./mvnw` wrapper; if absent, install
  or fall back to the version pinned in `.mvn/wrapper/maven-wrapper.properties`.
- `git apply` rejects a patch: regenerate it with `git diff` from a clean
  edit, or fall back to `patch -p1 < patch_i.diff`; never edit the repo
  without also updating the diff artifact.
- Build hangs or exceeds reasonable time: re-run with `-pl` scoped to the
  failing module plus `-am` to shorten the loop, but still run a full
  reactor build before the final stop-condition check.

## Anti-regression constraints

- Do not stop after the first green module while others still fail.
- Do not hard-code repo names, user names, or absolute paths beyond the
  `/home/travis/build/failed` root given by the task.
- Do not invent verifier requirements beyond the artifact contract above.
- Keep patches reversible: every change must live in a `patch_*.diff` that
  reproduces the applied edit.