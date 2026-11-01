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
   `/home/travis/build/failed/<org>/<repo>`.
## Minimal diagnostic sequence

Use a consistent reproduction workflow before editing files.

```bash
cd /home/travis/build/failed/<org>/<repo>

java -version
./mvnw -version || mvn -version

# Prefer the Maven wrapper when present
./mvnw -e clean test || mvn -e clean test

# Escalate diagnostics when the failure is unclear
./mvnw -X test || mvn -X test

# Multi-module targeting
./mvnw -pl <module> -am test || mvn -pl <module> -am test

# Bisect compilation vs test failures
./mvnw -DskipTests verify || mvn -DskipTests verify
```

Typical reproduction phases are `test` and `verify`; legacy builds and
integration-test-heavy projects may require `install` to populate the local
repository for downstream modules or invoker-based tests.
## General Maven lifecycle reminders



### Nested/Invoker integration test projects (`src/it`)

Legacy Maven projects often include nested integration-test projects under
`src/it`, `integration-tests`, or invoker fixture directories containing their
own `pom.xml` files.

- Locate nested POMs with commands such as `find . -name pom.xml`.
- Maven Invoker Plugin builds may require `mvn install` so tested artifacts are
  available from the local repository rather than only the current reactor.
- Review invoker-related configuration (`maven-invoker-plugin`, `invoker.properties`,
  custom profiles, or scripts) before assuming dependency resolution is broken.
- Use `-pl`/`-am` carefully when reproducing failures involving nested builds,
  because invoker projects may execute outside the main reactor.

Prefer fixing the root or module build configuration, dependency management, or
plugin setup first. Only edit nested test-project POMs when those fixtures are
source-controlled and intentionally require updates. Never edit generated
`target/` outputs or artifacts inside the local Maven repository.


### Toolchain selection

Before changing source code or `JAVA_HOME`, inspect the repository toolchain
configuration:

- Read `.mvn/jvm.config` if present.
- Inspect `maven-compiler-plugin` configuration for `release`, `source`, and
  `target` values.
- Check for Maven Toolchains usage (`toolchains.xml`, `maven-toolchains-plugin`,
  CI setup scripts).
- Prefer matching the JDK version required by the project instead of forcing an
  arbitrary local JDK.

Mismatched JDKs commonly cause CI-only failures, compiler API incompatibilities,
annotation processor issues, and inconsistent bytecode targets. Reproduce with
the intended toolchain before modifying build logic.
