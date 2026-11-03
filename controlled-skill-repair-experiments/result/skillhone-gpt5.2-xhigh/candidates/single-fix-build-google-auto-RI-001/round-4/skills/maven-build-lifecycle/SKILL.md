---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures (and when the task contract requires failed_reasons.txt + patch_*.diff artifacts).
---

# Maven Build Lifecycle — CI Repair Workflow

## SkillHone artifact contract (do this in every run)

This task family is evaluated on **build success** and on two explicit artifacts. Create them as files (not just as prose in chat).

### Required files

1. **Diagnosis note** (absolute path): `/home/travis/build/failed/failed_reasons.txt`
2. **One or more patch files** (absolute path, in repo root): `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (and `patch_2.diff`, …)

> Replace `<repo>` and `<id>` with the values from the task prompt. If you are already `cd`’d into the repo root, writing `patch_1.diff` in the current directory satisfies the required path.

### Quick templates (copy/paste)

Create the diagnosis note **early**, and update it as you learn more:

```bash
mkdir -p /home/travis/build/failed
cat > /home/travis/build/failed/failed_reasons.txt <<'EOF'
Toolchain
- java: <paste `java -version`>
- maven: <paste `./mvnw -v` or `mvn -v`>

Reproduction
- repo: /home/travis/build/failed/<repo>/<id>
- command: <exact mvn command that fails>
- first failing module/IT project: <module path or src/it/* path>

First real error
- <first compiler/test error line(s)>

Root cause hypothesis
- <why it fails>

Planned fix
- <what file(s) / pom changes you will make>
EOF
```

Generate a non-empty patch file from your changes:

```bash
# From the repo root (pom.xml present)
git diff --no-color > patch_1.diff
test -s patch_1.diff
```

To match the task’s “apply the diff” step, ensure the patch applies cleanly:

```bash
# Best done on a clean working tree
git apply --check patch_1.diff

git apply patch_1.diff
```

If `git apply` fails because you already edited files, either:
- revert to a clean tree (e.g., `git checkout -- .` or `git reset --hard`) and apply the patch, **or**
- keep the edits, but still provide a correct `patch_*.diff` that represents the final change.

## 1) Locate the repo root (don’t guess)

- The task prompt typically gives an exact path like `/home/travis/build/failed/<repo>/<id>`.
- `cd` to that directory and confirm it’s the Maven root:
  - `test -f pom.xml` should succeed.

If you are unsure where the root POM is, search for it, but avoid picking an unrelated nested `pom.xml` by accident (multi-module repos have many). Prefer the *top-level* one.

## 2) Toolchain selection (Maven + JDK)

### Maven

1. Prefer the Maven Wrapper (`./mvnw`) **if present and usable**; it often matches the project’s expected Maven version.
2. Fall back to system Maven (`mvn`) if the wrapper is missing **or fails to run** (e.g., wrapper download/network restrictions, missing wrapper JAR, permission issues).

Minimal robust snippet:

```bash
MVN=mvn
if [ -f ./mvnw ]; then
  MVN="./mvnw"
  [ -x ./mvnw ] || MVN="bash ./mvnw"
fi

# Validate the chosen Maven command; if wrapper fails, fall back.
$MVN -v || { MVN=mvn; mvn -v; }
```

### JDK

Record in your note:
- `java -version`
- the project’s expected release level (from `pom.xml` and/or CI config)

If you see errors like **"invalid target release"**, **"unsupported class file major version"**, or bytecode/version mismatches:

- Check `pom.xml` for `maven-compiler-plugin` configuration and properties such as:
  - `maven.compiler.release`, `maven.compiler.source`, `maven.compiler.target`
- Check CI configuration (e.g., `.travis.yml`, GitHub Actions) for the JDK version.
- Prefer switching to the expected JDK (e.g., via `JAVA_HOME` / `PATH`) rather than “papering over” the mismatch.
- If the project uses Maven Toolchains (`maven-toolchains-plugin`), follow that approach instead of ad-hoc environment changes.

## 3) Reproduce the failure the same way CI does

### Use the CI command first

- Mirror CI goals/profiles first; then narrow down once you know the first failing module.
- Find the exact Maven goals and profiles from CI config/logs (common examples: `test`, `verify`, `-P...`, `-D...`).
- Always include stack traces for diagnosis:
  - `-e -DtrimStackTrace=false`

If the CI command is unknown, start with a reasonable baseline and iterate:

```bash
# Prefer wrapper if available (see toolchain section)
$MVN -e -DtrimStackTrace=false clean test

# Near the end, consider a stricter check if CI runs it:
$MVN -e -DtrimStackTrace=false clean verify
```

### Narrow down for faster iteration

Once you know the first failing module, rerun narrowly:

```bash
# From the repo root, target a single module by artifactId and build its deps.
$MVN -e -DtrimStackTrace=false -pl :<artifactId> -am test
```

Tip: `-DskipTests` skips running tests but still compiles them; `-Dmaven.test.skip=true` skips compiling tests too. Use these only for *triage*—final verification should match CI/task expectations.

## 4) Maven Invoker failures: debug the nested project, not just the reactor

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

## 5) Dependency-drift signals in nested builds

Common symptoms that point to nested-build dependency/version drift:

- "cannot find symbol" for a class/method that exists in newer versions of a library
- test-only artifacts that are designed to be version-coupled (e.g., `<lib>` and `<lib>-testlib`) resolving to different versions
- `NoSuchMethodError` / `ClassNotFoundException` during tests even though the main reactor compiles

Prefer aligning versions/configuration in the nested POM (or via a BOM/import that the nested POM actually inherits) rather than rewriting valid source code to avoid an API.

## 6) Minimal diagnostic sequence (end-to-end)

```bash
# 0) Create/update the diagnosis note first
#    (see the template in the artifact contract section)

# 1) cd to the repo path from the task prompt
cd /home/travis/build/failed/<repo>/<id>

# 2) Select toolchain
MVN=mvn
if [ -f ./mvnw ]; then
  MVN="./mvnw"
  [ -x ./mvnw ] || MVN="bash ./mvnw"
fi
$MVN -v || { MVN=mvn; mvn -v; }
java -version

# 3) Reproduce
$MVN -e -DtrimStackTrace=false clean test

# 4) After implementing a fix, write a patch file and (re-)apply it if needed
git diff --no-color > patch_1.diff
test -s patch_1.diff

# 5) Verify again (match CI/task expectations)
$MVN -e -DtrimStackTrace=false clean test
```

## General Maven lifecycle reminders

- In multi-module projects, use the reactor summary to identify the first genuinely failing module, then inspect that module's own integration steps.
- Prefer minimal, targeted changes. Fix the root cause (dependency/config/toolchain drift) rather than masking errors by skipping build phases.
