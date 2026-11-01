---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Build-repair artifact contract

This benchmark requires both a diagnosis artifact and an applicable patch.
Before finishing:

1. Write the failure analysis, suspected root cause, and repair plan to
   `/home/travis/build/failed/failed_reasons.txt`.
2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/<org>/<repo>/patch_1.diff` (or `patch_{i}.diff`
   for multiple patches) containing the intended source or configuration
   change.
3. Apply the patch to the failed repository and ensure the repository working
   tree actually changes.
4. Run `git diff` and/or `git status` and verify that intended tracked project
   files changed, not only the generated patch artifact.
5. Do not hardcode repository-specific paths in commands or patch metadata;
   use the task-provided repository location under
   `/home/travis/build/failed/<org>/<repo>` (some tasks instead provide `/home/travis/build/failed/<repo>/<id>`; always `cd` into the task-provided path and avoid hardcoding either layout).
## Minimal diagnostic sequence

Use a consistent reproduction workflow before editing files.

### 0) Choose the build toolchain (order is intentional)

1. If the repo contains `./mvnw`, **prefer it** (it pins Maven and often repo-specific settings).
2. Otherwise use system `mvn`.
3. Record versions early (`java -version`, Maven version). Only change `JAVA_HOME` / toolchains when the failure clearly indicates a toolchain mismatch.

```bash
cd /home/travis/build/failed/<org>/<repo>   # or the task-provided /home/travis/build/failed/<repo>/<id>

java -version
if [ -x ./mvnw ]; then ./mvnw -version; else mvn -version; fi
```

### 1) Identify the correct Maven entrypoint (legacy/nested repos)

Not every repository builds from its VCS root. Before running large builds:

```bash
# Find candidate entrypoints
find . -maxdepth 4 -name pom.xml -not -path "*/target/*"

# If the root has no pom.xml, locate the actual aggregator (often under e.g. ./parent, ./build, ./maven)
ls -la
```

Prefer running Maven in the directory that contains the **aggregator** POM for the failing CI job (look for `<modules>` and CI scripts).

### 2) Reproduce with escalating phases/flags

Rules of thumb:
- Start with `clean test` for fast feedback.
- Use `verify` when integration-test plugins (Failsafe/Invoker) or additional checks run after `test`.
- Use `install` **only when needed** to seed the local repository for downstream/nested builds (Invoker, separate Maven executions, or builds that resolve artifacts outside the current reactor).

```bash
# Preferred command prefix
MVN="./mvnw"; [ -x ./mvnw ] || MVN="mvn"

$MVN -e -DtrimStackTrace=false clean test

# If failure is unclear, re-run the failing goal with more diagnostics
$MVN -e -DtrimStackTrace=false test
$MVN -X test

# If integration tests/checks are involved
$MVN -e clean verify

# Only if nested builds or downstream modules require artifacts from local repo
$MVN -e clean install

# Multi-module targeting (avoid rebuilding unrelated modules)
$MVN -e -pl <module-or-:artifactId> -am test

# Bisect compilation vs tests
$MVN -e -DskipTests verify
```

Typical reproduction phases are `test` and `verify`. Escalate to `install` when a later Maven execution (Invoker, scripts, separate module build) needs to resolve the just-built artifacts from the **local repository** rather than from the current reactor.
## General Maven lifecycle reminders



- Prefer the smallest phase that reproduces the CI failure (`test` → `verify` → `install`). Do not default to `install` unless you have evidence it is required.
- When fixing dependency/plugin issues, target the narrowest scope:
  - For multi-module builds, use `-pl`/`-am` to reproduce and validate fixes without rebuilding unrelated modules.
  - Avoid globally changing versions unless the root cause indicates a project-wide incompatibility.


### Nested/Invoker integration test projects (`src/it`)

Legacy Maven projects often include nested integration-test projects under `src/it`, `integration-tests`, or invoker fixture directories containing their own `pom.xml` files. These are often built by **a separate Maven execution** (outside the reactor), which changes how dependency resolution works.

#### Identify what is actually executed

- Locate nested POMs, but exclude generated directories:
  ```bash
  find . -name pom.xml -not -path "*/target/*" -not -path "*/.mvn/*"
  ```
- Inspect configuration before making assumptions:
  - `maven-invoker-plugin` / `maven-failsafe-plugin`
  - `invoker.properties`
  - profiles referenced by CI scripts
  - any `localRepositoryPath` / `localRepo` settings that redirect dependency resolution

#### Dependency resolution strategy (reactor vs local repository)

- If the nested/Invoker build is launched as a separate Maven process, it usually **cannot** see reactor-only artifacts and will resolve from the **local repository**.
- In that case, reproduce with `install` at the appropriate level to seed `~/.m2/repository` (or the configured local repo path):
  - Prefer `mvn -pl <module> -am install` instead of a full-repo install.
- If the integration tests run within the same Maven reactor (single execution), `verify` is typically sufficient; `install` may be unnecessary.

#### Targeted reproduction without overbuilding

- Use `-pl`/`-am` to build only the producing modules needed by the failing nested tests.
- Be cautious: Invoker can run in directories outside the reactor, so `-pl` may not affect what the invoker executes; verify by reading the plugin configuration/log output.

#### Safe-to-edit boundaries

- Prefer fixing the main build (root/module POMs, dependencyManagement, plugin configuration) rather than patching fixtures.
- Only edit nested test-project POMs when they are **version-controlled sources** (e.g., under `src/it/**` in the repository).
- Do **not** edit:
  - generated copies under `target/**` (including invoker clone directories such as `target/it/**`, `target/invoker/**`, `target/clone/**`)
  - anything inside the local Maven repository (`~/.m2/repository` or configured `localRepositoryPath`).


### Toolchain selection

Record the current toolchain first (`java -version`, Maven version). **Prefer using the repository-provided `./mvnw`** when available; it pins Maven behavior and may enforce required options.

Before changing source code, `JAVA_HOME`, or Maven settings, inspect the repo’s toolchain configuration:

- `.mvn/jvm.config` (extra JVM args used by Maven)
- `maven-compiler-plugin` (`release`/`source`/`target`)
- Maven Toolchains (`toolchains.xml`, `maven-toolchains-plugin`, CI scripts)

Only introduce toolchain overrides when the failure indicates a mismatch (e.g., classfile version errors, toolchain plugin failures). Avoid “fixing” builds by forcing arbitrary JDK/Maven versions without evidence, as that can mask the real issue and diverge from CI.
