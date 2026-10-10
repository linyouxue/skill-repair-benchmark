# Maven Build Failure Triage: Plugin vs Dependency vs JDK Artifacts

## Purpose
Provide a reusable workflow to diagnose and fix Maven build failures where the apparent symptom mentions plugins but the root cause is often dependency declaration, inherited POM configuration, or JDK-specific artifacts (for example, tools.jar on JDK 9+). The procedure prioritizes reproducing the repo entrypoint, locating the exact origin of the failing artifact/config, and applying the smallest safe POM change.

## When to Use
Use when a Maven build fails in CI or locally and the error mentions missing artifacts, system-scoped JARs, plugin execution failures, or JDK-dependent paths (notably references to tools.jar, com.sun:* coordinates, or a hardcoded JDK lib directory). Do not use as a general plugin configuration reference when there is no failing build signal.

## Procedure
- 1) Confirm the execution context before edits
- Discover how the repo expects the build to run:
- Prefer CI config (for example, .travis.yml, GitHub Actions) or documented commands.
- Identify any non-default POM file used (-f ...) and active profiles.
- Check toolchain basics without assuming versions:
- Record java -version and mvn -version (or the wrapper command if present).
- Checkpoint: You can state the exact build command you will run and the Java/Maven versions detected.
- 2) Reproduce the failure and capture the first failure signal (execution anchor)
- Run the repo-specified Maven command with minimal noise changes (avoid adding new flags unless needed to reproduce).
- Capture the first error that causes failure (not downstream cascades).
- If the failure mentions a missing artifact or path (example: com.sun:tools and .../lib/tools.jar), extract:
- groupId:artifactId:packaging:version
- any referenced filesystem path (systemPath) and which JDK it points to
- Checkpoint: You have a single, precise failure signature to trace.
- 3) Trace where the failing artifact/config is introduced (execution anchor)
- Ground in the actual project structure:
- Locate the relevant pom.xml files (root and modules) and any parent POM references.
- Identify the introducer using Maven diagnostics (choose what exists in the environment):
- Preferred: generate effective POM for the failing module (help:effective-pom) and search it for the failing coordinates (groupId/artifactId).
- Also useful: dependency tree filtered to the failing coordinates (dependency:tree with includes/filtering).
- Decide the origin category:
- Direct dependency in a module POM
- Inherited from parent or dependencyManagement
- Transitive dependency pulled by another library
- Plugin dependency or plugin configuration (less common for tools.jar issues)
- Checkpoint: You can point to the exact POM location (file and section) that declares or forces the failing artifact.
- 4) Apply the smallest fix that removes the failing requirement, then re-check (execution anchor + bounded fallback)
- If the failure is tools.jar / com.sun:tools on JDK 9+:
- Prefer removing the requirement rather than inventing a tools.jar path.
- Choose the smallest applicable remedy based on origin:
- If transitive: add an exclusion on the dependency that pulls it in.
- If direct/system-scoped: remove it, or replace/upgrade the library that requires it to a version compatible with JDK 9+.
- If needed only for specific JDKs: gate the dependency with a profile activated only on older JDKs (do not assume JDK numbers; use the detected runtime).
- Re-run the smallest Maven step that previously failed (for example, the same phase/goal up to the failure point).
- Bounded fallback branch (fallback-after-tool-failure):
- If the same missing tools.jar/com.sun:tools error repeats after your change, stop editing plugins and:
- Re-run effective POM/dependency tree and search again for any remaining declaration sources (multiple modules can introduce it).
- Apply exactly one more minimal change (next introducer), then re-run the minimal failing check.
- If it still repeats, escalate to method-level: propose a targeted upgrade/replace of the introducing library or a JDK-conditional profile strategy, and do not continue random version pinning.

## Constraints / Pitfalls
- Do not hard-code Java release levels, plugin versions, or filesystem paths unless they are already present in the repo and verified by discovery; prefer aligning with existing POM constraints and only changing what the traced origin requires.
- Do not respond to a dependency/path resolution error by only tuning plugins (surefire/compiler/enforcer) without first proving via effective POM/dependency tree where the failing coordinate is introduced; otherwise you risk repeated failures and irrelevant churn.