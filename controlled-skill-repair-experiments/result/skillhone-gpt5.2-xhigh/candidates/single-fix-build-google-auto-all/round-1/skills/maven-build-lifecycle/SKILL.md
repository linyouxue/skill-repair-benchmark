---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — CI Repair Workflow

Use this skill to **reproduce** a failing Maven build locally, **isolate** the failing module/phase, and **apply** a minimal fix while producing the artifacts required by the task prompt.

## Build-repair artifact contract (follow the prompt)

Many tasks in this benchmark require both a diagnosis note and a patch artifact.

Before finishing, confirm the prompt’s required paths and do all of the following:

1. **Write analysis + plan** to the required diagnosis file (commonly:
   `/home/travis/build/failed/failed_reasons.txt`).
2. **Create at least one non-empty unified diff** at the required patch path
   (commonly:
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff`) containing the intended
   source/config change.
3. **Apply the patch** to the repository.
4. Verify the repository contents changed (not just the patch file):
   `git diff` / `git status`.

> Keep paths **parameterized**. Do not hard-code a specific repository name/id in
> your workflow; always use the location given by the task.

## 1) Choose the correct build toolchain

### Prefer the Maven Wrapper when present

From the repository root, check for a wrapper:

- `./mvnw` (Unix)
- `.mvn/wrapper/maven-wrapper.properties`

If present, prefer:

```bash
./mvnw -v
./mvnw -B -e test
```

Reason: the wrapper pins a Maven distribution compatible with the project (common
in older or plugin-heavy builds).

If no wrapper exists, use the system Maven:

```bash
mvn -v
mvn -B -e test
```

### Confirm the Java version requirements

Build failures often come from a **Java/Maven mismatch** rather than code.

Checklist:

- Look for `maven-compiler-plugin` configuration (`<source>`, `<target>`,
  `<release>`), `maven-toolchains-plugin`, or `maven-enforcer-plugin`
  `requireJavaVersion`.
- Ensure you run Maven with the expected JDK (via `JAVA_HOME`/`PATH` as provided
  by the environment). Avoid “fixing” by globally changing toolchains unless the
  project explicitly requires it.

## 2) Reproduce the failure (baseline commands)

Start with a command that matches Maven’s standard lifecycle and produces useful
logs:

```bash
# Fast signal: compile + unit tests
mvn -B -e test

# Full build signal (includes integration-test/verify where configured)
mvn -B -e verify
```

Conventions:

- Use `-B` (batch) to reduce interactive noise.
- Add `-e` to include exception stack traces.
- Only use `-X` (debug) after you’ve narrowed the failing area.

If the project is multi-module, run from the **root aggregator POM** (the one
listing `<modules>`).

## 3) Isolate the failing module, phase, or test

### Identify the failing module

When Maven prints “Reactor Summary” it shows which module failed.
Common narrowing patterns:

```bash
# Build only one module and whatever it depends on
mvn -B -e -pl :<artifactId> -am test

# Resume from a failing module
mvn -B -e -rf :<artifactId> test
```

### Separate compilation from tests

To decide whether you’re dealing with compilation vs tests vs packaging:

```bash
# Compilation only
mvn -B -e -DskipTests compile

# Run a single test (Surefire)
mvn -B -e -Dtest=<TestClass> test
```

Use skipping flags only as **diagnostic tools** unless the prompt explicitly
allows skipping.

## 4) Special case: Maven Invoker / nested test projects

Legacy plugin builds frequently use `maven-invoker-plugin` to run integration
tests that build **nested sample projects**.

### How to recognize it

Look for `maven-invoker-plugin` in the root POM (or a plugin module POM) and
directories such as:

- `src/it/...`
- `src/it/projects/...`
- `src/it/<test-name>/pom.xml`

### Key rule: edit the *source* of the nested projects

Invoker tests typically copy projects into `target/it` (or similar) at runtime.

- Do **not** patch generated copies under `target/`.
- Patch the checked-in templates under `src/it/` (or the configured invoker
  clone directory).

### Dependency resolution in nested projects

If a nested project fails because it can’t resolve dependencies/plugins:

- Confirm whether it should resolve artifacts from the **current reactor**
  (`${project.version}`, `-pl/-am`, local repo usage) or from remote repos.
- Prefer fixes that keep builds reproducible:
  - ensure nested POMs inherit/align versions via properties
  - avoid adding ad-hoc remote repositories unless the build already depends on
    them
- Keep the scope of changes minimal:
  - If only integration test templates are broken, change `src/it/**`.
  - If the plugin under test publishes/installs an artifact needed by invoker
    tests, ensure the main build phase produces it before invoker runs (often a
    lifecycle ordering/config issue).

## 5) Apply a minimal fix and validate

After implementing a change:

1. Re-run the smallest command that demonstrates the fix (often `-pl … -am test`).
2. Re-run the broader lifecycle phase that originally failed (`test` or `verify`).
3. Ensure no unintended files changed (avoid committing `target/`, downloaded
   artifacts, IDE files).

If the failure is build-configuration related, consider reviewing:

- `dependencyManagement` alignment (see skill: `maven-dependency-management`)
- plugin versions/config (`maven-plugin-configuration`)
- enforcer rules and toolchains

## Troubleshooting quick hits

- **Maven can’t find a parent POM / wrong module directory**: ensure you’re in
  the correct root and not a submodule.
- **Tests are flaky or environment-dependent**: isolate with `-Dtest=...` and
  confirm whether the failure is deterministic.
- **Invoker failures**: check the invoker log directory (configured by the
  plugin) and ensure you’re editing templates, not copied projects.
