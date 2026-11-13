---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

## Steps
1. **Enter the correct repo and pick a Maven executable that won’t get stuck downloading tooling**
   - `cd /home/travis/build/failed/<repo>/<id>` (use the task-provided path).
   - If `./mvnw` exists, prefer it **only if it can run without fetching a Maven distribution** (quick check: `./mvnw -v`). If the wrapper fails due to downloads, fall back to system `mvn`.
   - Record environment context early (`java -version`, `echo "$JAVA_HOME"`, `mvn -v` or `./mvnw -v`) so you can reason about JDK-/Maven-specific failures.

2. **Reproduce the failure with the CI-equivalent Maven command (then iterate on the failing module)**
   - Run from the reactor root using the lifecycle that will exercise CI checks (commonly `verify` for projects with invoker/failsafe/integration tests; otherwise `test`).
   - Use `-e` (and `-X` only when needed) so logs contain actionable stack traces and the *first* real error.
   - If the build is slow, iterate with the failing module to avoid timeouts: `mvn -e -pl <failing-module> -am verify` (still do a final full reactor `verify` at the end).
   - If you see dependency/plugin download/transfer failures in an offline/blocked CI environment:
     - First check the pre-populated Maven user cache (e.g., `/home/travis/.m2/repository/...`); don’t assume any system Maven repo includes core plugins.
     - If the needed artifacts exist in `/home/travis/.m2/repository`, create/update repo-root `.mvn/maven.config` to force reuse of that cache (typical contents: `-o -Dmaven.repo.local=/home/travis/.m2/repository`), then rerun to reach the *real* build failure.

3. **Write diagnosis + plan to the required note file**
   - Create/update `/home/travis/build/failed/failed_reasons.txt` with:
     - the exact failing Maven command,
     - the first fatal error (copy the key lines),
     - whether it’s primarily **code** vs **build configuration/dependency/toolchain**,
     - which module(s) / phase(s) fail,
     - a concrete fix plan and how you’ll verify it.

4. **Scope the failure correctly (root vs module vs nested invoker projects)**
   - Use the reactor summary to identify which module triggers the failure.
   - If the build uses Maven Invoker / nested test projects, also locate nested `pom.xml` under typical invoker directories (e.g., `src/it/**`) because those projects resolve dependencies independently and may require parallel fixes (parent/version alignment, dependency exclusions) and/or explicit offline/local-repo settings passed through the invoker configuration.

5. **Diagnose dependency/parent problems using reliable discovery (no brittle path guesses)**
   - For **missing parent / offline-only** failures: inspect the root `pom.xml` `<parent>` and every module’s `<parent>`; if an external parent is unavailable offline, remove/replace it and align *all* modules to an in-repo parent/version (don’t fix just one POM).
   - For **transitive dependency** failures: use `mvn dependency:tree` filtering to the problematic coordinate (add `-pl <module> -am` to focus), and when needed inspect the resolved POM in the local repository (`/home/travis/.m2/repository/.../*.pom`) to find the *true* source stanza.
   - For repository-wide searches, enumerate/target real POMs instead of typing paths from memory (`git ls-files '**/pom.xml'` or `find . -name pom.xml`), then search with `rg -n` (or `grep -R --line-number`).
   - Run searches independently; avoid `cmd1 && cmd2` chains where a no-match (exit code 1) prevents subsequent searches and can hide additional occurrences.

6. **Apply fixes consistently across the whole build (multi-module + nested test projects)**
   - If a dependency/plugin configuration is present in multiple modules, either:
     - centralize the fix in the shared parent (`dependencyManagement` / `pluginManagement`), **or**
     - apply the same change to **every** module POM (and any nested invoker project POMs) that declares it.
   - After editing, re-run the same repo-wide search to confirm there are no remaining unpatched declarations.

7. **Handle JDK9+ `tools.jar` / `com.sun:tools` failures end-to-end**
   - When Maven fails on `com.sun:tools` / `tools.jar`, first locate the *declaring* POM (repo search for `com.sun:tools`, `tools.jar`, and/or `<systemPath>`, plus `mvn -pl <module> -am dependency:tree -Dincludes=com.sun:tools` to identify the introducer).
   - If the dependency is declared in this repo, remove it from the default dependency set and make it **JDK8-and-earlier only** (e.g., move it into a profile activated for `<jdk>[1.0,1.9)</jdk>`), since JDK9+ has no `tools.jar`.
   - If it comes from a third-party dependency, prefer upgrading that dependency to a JDK9+ compatible version; otherwise exclude `com.sun:tools` where it is brought in and, if compilation/tests still need compiler classes, add the necessary JDK9+ module flags via plugin configuration (commonly `--add-modules jdk.compiler`).
   - Apply the fix anywhere it can bite: all reactor modules **and** any `src/it/**` invoker project POMs.

8. **Create patch artifacts (capturing all edits), then apply them, then verify**
   - After finishing *all* edits (including new files like `.mvn/maven.config`), confirm what changed: `git diff --stat`.
   - Draft the required unified diff file(s) inside the repo: `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff` (e.g., `git diff > patch_1.diff`; ensure it is non-empty and contains *all* intended edits). If you make further edits after writing a patch, regenerate the patch file(s) (or add `patch_2.diff`, etc.) so patches match the final repo state.
   - Apply your diff file(s) to the repository (e.g., revert tracked changes if needed, then `git apply patch_*.diff`) so the repo state corresponds to the patch artifacts.
   - Re-run the full Maven build command used to reproduce the failure and do not stop until it succeeds.
   - Final sanity: `git status` shows intended project-file changes, patch file(s) exist, and `/home/travis/build/failed/failed_reasons.txt` matches the final root cause + fix.

## Expected Result
You can (1) reproduce the original Maven failure, (2) document a clear root cause + plan in `failed_reasons.txt`, (3) implement fixes that cover all affected modules/nested test projects, (4) generate `patch_{i}.diff` files that fully capture the changes, and (5) apply those patches and pass the final Maven build.
