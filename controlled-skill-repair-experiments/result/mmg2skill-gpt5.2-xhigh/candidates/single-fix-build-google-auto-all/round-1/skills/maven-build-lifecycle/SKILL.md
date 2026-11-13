---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

## Steps
1. **Enter the correct repo and select the Maven toolchain**
   - `cd /home/travis/build/failed/<repo>/<id>` (use the task-provided path).
   - Prefer the Maven Wrapper if present: use `./mvnw` (or `./mvnw -q`) when it exists and is executable; otherwise use `mvn`.
   - Record environment context early (`java -version`, `mvn -version`) so you can reason about JDK-specific failures.

2. **Reproduce the failure with the CI-equivalent Maven command**
   - Run from the root of the multi-module build (reactor) using the lifecycle that will exercise CI checks (commonly `verify` for projects with invoker/failsafe/integration tests; otherwise `test`).
   - Use `-e` (and optionally `-X` if needed) so logs contain actionable stack traces and the *first* real error.
   - If you see dependency download/transfer failures in an offline CI environment, force offline builds via `.mvn/maven.config` (e.g., include `-o` and a fixed `-Dmaven.repo.local=...` pointing at an existing/writable cached repo), then rerun to get the *real* build failure.

3. **Write diagnosis + plan to the required note file**
   - Create/update `/home/travis/build/failed/failed_reasons.txt` with:
     - the exact failing Maven command,
     - the first fatal error (copy the key lines),
     - whether it’s primarily **code** vs **build configuration/dependency/toolchain**,
     - which module(s) / phase(s) fail,
     - a concrete fix plan and how you’ll verify it.

4. **Scope the failure correctly (root vs module vs nested invoker projects)**
   - Use the reactor summary to identify which module triggers the failure.
   - If the build uses Maven Invoker / nested test projects, also search for nested `pom.xml` under typical invoker directories (e.g., `src/it/**`) because those projects resolve dependencies independently and may require parallel fixes or configuration (offline/local-repo settings, dependency adjustments).

5. **Diagnose dependency/parent problems using reliable discovery (no brittle searches)**
   - For **missing parent / offline-only** failures: inspect the root `pom.xml` `<parent>` and every module’s `<parent>`; if an external parent is unavailable offline, remove/replace it and align *all* modules to an in-repo parent/version (don’t fix just one POM).
   - For **transitive dependency** failures: use `mvn dependency:tree` filtering to the problematic coordinate, and when needed inspect the resolved POM in the local repository (`~/.m2/repository/.../*.pom`) to find the *true* source of the bad dependency declaration.
   - For repository-wide searches, prefer `rg -n` (or `grep -R --line-number`) and run searches independently; avoid `cmd1 && cmd2` chains where a no-match (exit code 1) prevents subsequent searches and can hide additional occurrences.

6. **Apply fixes consistently across the whole build (multi-module + nested test projects)**
   - If a dependency/plugin configuration is present in multiple modules, either:
     - centralize the fix in the shared parent (`dependencyManagement` / `pluginManagement`), **or**
     - apply the same change to **every** module POM (and any nested invoker project POMs) that declares it.
   - After editing, re-run the same repo-wide search to confirm there are no remaining unpatched declarations.

7. **Handle JDK9+ `tools.jar` / `com.sun:tools` failures end-to-end**
   - When Maven fails on `com.sun:tools` / `tools.jar`, confirm the environment truly lacks `tools.jar` (JDK 9+), then determine which dependency introduces it (often via test utilities like `compile-testing`) by dependency-tree inspection and/or reading the resolved POM.
   - Fix by excluding the offending transitive dependency (e.g., exclude `com.sun:tools`) in a way that covers **all** modules/test-projects that use the introducing dependency (or centralize the exclusion in the parent so nothing is missed).

8. **Create patch artifacts, then apply them, then verify**
   - Draft the required unified diff file(s) inside the repo: `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff` (e.g., `git diff > patch_1.diff`; ensure it is non-empty and contains *all* intended edits).
   - Apply your diff file(s) to the repository (e.g., reset to clean if needed, then `git apply patch_*.diff`) so the repo state corresponds to the patch artifacts.
   - Re-run the full Maven build command used to reproduce the failure and do not stop until it succeeds.
   - Final sanity: `git status` shows intended project-file changes, patch file(s) exist, and `/home/travis/build/failed/failed_reasons.txt` matches the final root cause + fix.

## Expected Result
You can (1) reproduce the original Maven failure, (2) document a clear root cause + plan in `failed_reasons.txt`, (3) implement fixes that cover all affected modules/nested test projects, (4) generate `patch_{i}.diff` files that fully capture the changes, and (5) apply those patches and pass the final Maven build.
