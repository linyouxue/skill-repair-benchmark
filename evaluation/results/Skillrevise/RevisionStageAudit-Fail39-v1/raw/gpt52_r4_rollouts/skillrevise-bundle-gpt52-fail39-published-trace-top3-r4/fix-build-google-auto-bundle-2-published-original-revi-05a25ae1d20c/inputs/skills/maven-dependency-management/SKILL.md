# Maven Build Dependency Fix Loop (Repo-Grounded)

## Purpose
Provide a tight, repeatable workflow to diagnose and fix Maven dependency and toolchain-related build failures in a concrete repository by reproducing the exact failing command, proving dependency resolution changes, applying the smallest safe edit, and verifying by rerunning the same build.

## When to Use
Use when a Maven build/test is failing (locally or in CI) and the likely root cause involves dependency resolution, plugin/toolchain compatibility (especially JDK 9+ changes like tools.jar removal), BOM/dependencyManagement alignment, exclusions, or version overrides. Do not use as a general Maven tutorial or for tasks that do not require editing a real repo and verifying a build.

## Procedure
- 1) Reproduce with the exact build command (execution anchor)
- Discover the authoritative invocation: CI log, task instructions, or project docs. Preserve flags, selected POM (-f), profiles (-P), and properties (-D...).
- Run it once without modifications. Record ONLY the first failure signature: failing module, failing plugin goal, or failing test class plus the topmost error message.
- 2) Classify the failure and confirm current resolution before editing (execution anchor)
- If the error mentions missing artifact/classes, version conflicts, linkage errors, or unexpected transitive jars: treat as dependency resolution.
- If it mentions tools.jar, com.sun:tools, javax.tools, or system-scoped jar paths: treat as JDK 9+ toolchain mismatch.
- Confirm what Maven is actually using BEFORE changing anything:
- Run `mvn help:effective-pom` and/or `mvn dependency:tree` (filter to the suspicious groupId/artifactId if known).
- Capture the resolved version/scope/source (managed vs direct) for the problematic dependency or plugin.
- 3) Choose the smallest viable remediation (decision point)
- Prefer (in order) changes that are easiest to reason about and verify:
- Align/upgrade via `dependencyManagement` (or an existing BOM) so the whole reactor uses one compatible version.
- Upgrade/replace the specific offending dependency/plugin to a version compatible with the current JDK/build.
- Add a targeted exclusion ONLY if you can name the transitive edge and you will add/keep a supported replacement.
- Add toolchain/profile gating only when the project must support multiple JDKs.
- JDK 9+ tools.jar mismatch branch:
- Do NOT add system-scoped references to tools.jar.
- Prefer upgrading/removing the dependency/plugin that expects tools.jar or com.sun:tools.
- If the project must compile with a specific JDK, use Maven toolchains (or documented CI JDK selection) rather than hard-coded jar paths.
- 4) Apply one minimal change, prove it took effect, then re-run (bounded loop) (execution anchor)
- Make a single focused edit (one POM or one managed version block) and keep it minimal.
- Prove the change impacted resolution BEFORE full tests:
- Re-run `mvn -q -DskipTests dependency:tree` (or effective-pom) and confirm the resolved version/scope/path changed exactly as intended.
- Then re-run the exact build command from step 1.
- If the same failure persists after one minimal fix:
- Fallback (bounded) per failure signal:
- If resolution did not change as intended: fix the management location (parent vs module), conflicting overrides, or profile activation; re-run ONLY the resolution proof check.
- If resolution changed but failure persists: pivot once to the next least invasive alternative from step 3 (typically align/upgrade rather than adding more exclusions), then repeat prove -> rerun.
- Stop after two remediation attempts for the same signature; escalate by re-checking classification (dependency vs toolchain vs code/test) and re-identifying the first failing artifact.

## Constraints / Pitfalls
- Never hard-code system paths (for example, tools.jar) or assume a specific JDK layout; require discovery evidence (effective-pom/dependency:tree and observed JDK behavior) before any toolchain-related change.
- Do not run heavyweight cache purges or broad updates (for example, purge-local-repository, -U everywhere) unless there is direct evidence of corrupted or stale artifacts; prefer targeted resolution proof checks and minimal POM edits.