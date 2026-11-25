---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

This skill focuses on **reproducible diagnosis** and **minimal, evidence-driven fixes** for Maven builds, including projects that run nested builds via `maven-invoker-plugin`.

## 0) Toolchain selection (make the failure reproducible)

1. **Prefer Maven Wrapper if present** (it pins Maven and often JDK/toolchain expectations):

```bash
# from repo root
if [ -x ./mvnw ]; then MVN=./mvnw; else MVN=mvn; fi
```

2. **Record tool versions** in your notes (so the failure can be re-run exactly):

```bash
java -version
$MVN -v
```

If the build fails with Java release/target errors (`invalid target release`, `release version X not supported`), treat it as a **toolchain mismatch** until proven otherwise.

## 1) Reproduce the failure with the correct lifecycle phase

Use a single “baseline” command first, with evidence-friendly flags:

```bash
$MVN -e -DtrimStackTrace=false verify | tee /tmp/build.log
```

Why `verify` by default?
- Many projects bind **integration tests**, **Failsafe**, or **Invoker** executions to `verify`.
- Running only `test` may miss the phase where CI fails.

If you have strong evidence the project is unit-test-only, you can try:

```bash
$MVN -e -DtrimStackTrace=false test | tee /tmp/build.log
```

Always extract and act on the **first actionable error** (compiler error / test stack trace / enforcer rule), not the Maven summary.

## 2) Maven Invoker failures: debug the nested project, not just the reactor

`maven-invoker-plugin` can launch independent Maven builds from directories such as
`src/it/<case>/` containing their own `pom.xml`. These nested builds have **independent dependency resolution** and can fail even when the main reactor succeeds.

If Maven reports output similar to:

```text
The following builds failed:
*  <some-it>/pom.xml
```

then:

1. Locate the exact integration-test POM/directory referenced by Invoker output.
2. Open the corresponding Invoker `build.log` (it often contains the *real* compiler/test error).
3. Identify the *first concrete compiler/test error* inside that nested build.
4. Inspect that nested POM’s **direct dependencies**, **plugin config**, and **properties**.
5. Re-run the nested build directly (to iterate faster than the full reactor).
6. Fix the nested dependency/configuration drift instead of broad-editing unrelated top-level modules.

Do not assume versions declared in the parent reactor automatically govern an Invoker integration-test POM. Integration-test POMs that were copied or maintained separately can become stale.

### Finding Invoker logs

Common locations include:

```bash
find . -type f \( -name build.log -o -name invoker.properties -o -name pom.xml \) \
  | grep -E '/target/it/|/src/it/'

# Often the most useful:
find . -type f -path '*/target/it/*/build.log' -print
```

If the nested build failed but the console output is too thin, consider re-running the **top-level** build with Invoker log streaming enabled (when supported by the project’s Invoker plugin configuration):

```bash
# Optional: stream nested build output to the main Maven console
$MVN -e -DtrimStackTrace=false -Dinvoker.streamLogs=true verify | tee /tmp/build.log
```

(If `-Dinvoker.streamLogs=true` has no effect, check the project’s `maven-invoker-plugin` configuration for an equivalent property name or a hard-coded `<streamLogs>` setting.)

### Re-running a nested Invoker project directly

Once you identify an IT directory containing a `pom.xml`:

```bash
cd <path-to-it-directory>
$MVN -e -DtrimStackTrace=false verify | tee /tmp/it-build.log
```

This isolates the failing build and makes dependency/plugin issues easier to see.

## 3) Missing classes/symbols usually indicate dependency-version drift

For a compiler error such as:

```text
cannot find symbol: class <SomeClass>
location: package <some.package>
```

first determine which version the failing module/nested build actually selected.
A “missing API” is often a version signal: a stale or transitively selected dependency can make otherwise-correct sources fail.

For libraries designed to be version-coupled (e.g., a core library and its testlib), prefer an explicit, synchronized dependency set.
Do not “fix” valid source by rewriting it to avoid the missing API unless the source itself is demonstrated to be wrong.

Helpful commands (run at the *failing* module / nested build root):

```bash
$MVN -q -DskipTests dependency:tree
$MVN -q -DskipTests help:effective-pom
```

## 4) Build-repair artifact contract (SkillTTA workflow)

This benchmark requires both a diagnosis artifact and an applicable patch.
Before finishing:

1. Write `/home/travis/build/failed/failed_reasons.txt` including:
   - repo path: `/home/travis/build/failed/<repo>/<id>`
   - toolchain (`java -version`, `$MVN -v`)
   - exact repro command used
   - failing module or nested IT directory
   - the first actionable error snippet
   - root cause classification (code vs build config)
   - minimal fix plan + verification command

2. Create at least one non-empty unified diff at:

   `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`

3. Apply the patch to the repository and confirm the repo files changed (not only the patch artifact).

4. Verify by re-running the **same command** used to reproduce the failure.

## 5) Minimal diagnostic sequence (generic)

```bash
cd /home/travis/build/failed/<repo>/<id>

# Toolchain capture (for failed_reasons.txt)
java -version
if [ -x ./mvnw ]; then MVN=./mvnw; else MVN=mvn; fi
$MVN -v

# Reproduce with evidence-rich flags
$MVN -e -DtrimStackTrace=false verify | tee /tmp/build.log

# Quickly surface actionable errors
grep -nE "\[ERROR\]|COMPILATION ERROR|Failed to execute goal|cannot find symbol|package .* does not exist|There are test failures" /tmp/build.log | head -n 120

# If Invoker is involved, locate nested build logs
find . -type f -path '*/target/it/*/build.log' -print
```

## 6) General Maven lifecycle reminders

- In multi-module builds, use the reactor summary to locate the *first* failing module.
- For test failures, prefer reading the module’s reports:
  - Surefire: `target/surefire-reports/`
  - Failsafe: `target/failsafe-reports/`
- Avoid disabling tests or skipping phases unless the project explicitly allows it and the change is justified by evidence.
