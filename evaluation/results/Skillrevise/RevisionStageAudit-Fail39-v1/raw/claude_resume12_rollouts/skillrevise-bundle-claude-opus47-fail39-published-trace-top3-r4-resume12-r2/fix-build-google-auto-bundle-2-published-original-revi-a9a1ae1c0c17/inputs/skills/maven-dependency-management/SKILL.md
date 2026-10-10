# maven-build-failure-repair

## Purpose
Reusable workflow for diagnosing and fixing a failing Maven build (local or CI) by first reproducing the exact failing command, grounding the environment (JDK, Maven, project source/target), classifying the failure, and applying the minimal correct fix before touching sources or versions.

## When to Use
Use when a Maven project build or CI job is failing and the task is to make it pass. Do NOT use for: authoring a new pom from scratch, greenfield dependency selection on a passing build, or non-Maven JVM builds (Gradle, sbt, Bazel).

## Procedure
- Discover the build contract. Locate the repo root (file `pom.xml` present). Read CI config (`.travis.yml`, `.github/workflows/*.yml`, `Jenkinsfile`, etc.) and extract the verbatim build command, including flags and `-f` pom path. Do not guess; copy it.
- Record the environment. Run `java -version`, `mvn -v`, and `mvn -f <pom> help:effective-pom | head` to capture active JDK major version, Maven version, and project `maven.compiler.source`/`target` or `java.version`. Save these as the baseline.
- Reproduce the failure. Run the exact CI command unchanged. Capture: exit code, first failing phase (compile, test, package), failing class/test names, and the top stack frame or Maven error code.
- Classify the failure into exactly one primary bucket before editing anything:
- compile_error: `javac` or annotation-processor failure.
- missing_or_conflicting_dep: `Could not resolve`, `NoClassDefFoundError`, convergence error.
- test_failure: compiles, surefire/failsafe reports assertion or runtime failure.
- env_mismatch: references to `tools.jar`, `com.sun:tools`, `javax.annotation.Generated`, `sun.misc.*`, or JDK-removed APIs while active JDK differs from project source/target.
- Choose fix path by class:
- env_mismatch and active JDK greater than project target: prefer installing/selecting a matching JDK via `maven-toolchains-plugin` or environment JDK switch; alternatively upgrade the offending library (e.g., annotation-processor, compile-testing) to a version supporting the active JDK. Do these BEFORE adding exclusions.
- missing_or_conflicting_dep: use `mvn dependency:tree -Dverbose` and `mvn dependency:analyze` to identify, then pin via `<dependencyManagement>` or import a BOM. Add `<exclusions>` only for identified duplicates.
- compile_error from third-party API drift: pin or upgrade the single offending artifact; do not bulk-bump.
- test_failure: inspect surefire report under `target/surefire-reports/`; fix cause, do not disable tests to pass.
- Apply the minimal patch. Edit only pom files or toolchain config needed for the chosen fix. Keep each patch to one logical change.
- Verify loop (bounded, one re-classification): re-run the exact CI command from step 1. If it passes, stop. If it fails with the same failing symbols, re-run step 4 to re-classify (the first classification may have been wrong) and pick a different fix path. If it fails with new symbols, treat as progress and continue. Abort after the second unsuccessful re-classification and report findings instead of guessing further.

## Constraints / Pitfalls
- Do NOT edit application sources or tests before step 3 confirms the failure reproduces locally with the exact CI command.
- Do NOT add `<scope>system</scope>` dependencies or hard-coded `systemPath` entries; they break portability.
- Do NOT bump unrelated dependency versions, change `maven.compiler.source/target`, or add `<java.version>` overrides to mask an environment mismatch; fix the toolchain or the specific library instead.
- Do NOT skip or `@Disabled` failing tests to make the build green unless the task explicitly permits it.
- Always re-run the exact CI command (same flags, same `-f` pom) after each patch; a passing `mvn clean install` from the repo root does not prove the CI command passes.
- Treat `tools.jar`, `com.sun:tools`, and `javax.annotation.Generated` references as strong signals of a JDK 8 vs 9+ mismatch, not as transitive-dependency bugs.
- Prefer `<dependencyManagement>` and BOM imports over per-dependency `<version>` and `<exclusions>` when fixing conflicts.