---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

## Steps
1. **Locate and enter the real checkout (`/home/travis/build/failed/<repo>/<id>`) and choose Maven without wrapper downloads**
   - If `<repo>/<id>` aren’t explicitly known, discover them by listing down from the failed workspace until you reach the leaf directory that contains the build root (`pom.xml`, `.git`, `mvnw`):
     - `ls -la /home/travis/build/failed` → pick `<repo>`
     - `ls -la /home/travis/build/failed/<repo>` → pick `<id>`
   - `cd /home/travis/build/failed/<repo>/<id>` and confirm you’re at the reactor root: `pwd; ls -la; test -f pom.xml`.
   - Prefer system Maven (`mvn -v`). If `./mvnw` exists, use it only when `./mvnw -v` succeeds immediately (no Maven distribution download); otherwise stick with `mvn`.

2. **Create the required note file immediately and capture toolchain context**
   - Ensure `/home/travis/build/failed/failed_reasons.txt` exists from the start (then keep updating it as you learn more):  
     `: > /home/travis/build/failed/failed_reasons.txt`
   - Capture context that commonly explains CI-only failures:
     - `java -version`
     - `javac -version`
     - `echo "$JAVA_HOME"`
     - `mvn -v` or `./mvnw -v`
     - repo path: `pwd`

3. **Reproduce the failure with the CI-equivalent Maven command (then iterate on the failing module)**
   - Prefer the project’s CI command when it exists (commonly `.travis.yml`, GitHub Actions workflows, etc.); run that exact Maven goal/options from the reactor root.
   - If no explicit CI command is found, start with `mvn -B -e verify` (or `test` when the project clearly has no integration-test phase).
   - Use `-e` (and `-X` only when needed) so logs contain actionable stack traces and the *first* real error.
   - If the build is slow, iterate with the failing module to avoid timeouts: `mvn -B -e -pl <failing-module> -am verify` (still do a final full reactor `verify` at the end).
   - If you see dependency/plugin download/transfer failures in an offline/blocked CI environment:
     - First check the pre-populated Maven user cache (e.g., `/home/travis/.m2/repository/...`); don’t assume any system Maven repo includes core plugins.
     - If the needed artifacts exist in `/home/travis/.m2/repository`, create/update repo-root `.mvn/maven.config` to force reuse of that cache (typical contents: `-o -Dmaven.repo.local=/home/travis/.m2/repository`), then rerun to reach the *real* build failure.

4. **Update `failed_reasons.txt` with the first fatal error + a concrete fix plan**
   - In `/home/travis/build/failed/failed_reasons.txt`, record:
     - the exact failing Maven command you ran,
     - the first fatal error (copy the key lines),
     - whether it’s primarily **code** vs **build configuration/dependency/toolchain**,
     - which module(s) / phase(s) fail,
     - a concrete fix plan and how you’ll verify it (final Maven command to run).

5. **Scope the failure correctly (root vs module vs nested invoker projects)**
   - Use the reactor summary to identify which module triggers the failure.
   - If the build uses Maven Invoker / nested test projects, locate the *source* nested `pom.xml` under typical invoker directories (e.g., `src/it/**/pom.xml`), not generated copies under `target/**`. Those projects resolve dependencies independently and may require parallel fixes (parent/version alignment, dependency exclusions) and/or explicit offline/local-repo settings passed through the invoker configuration.

6. **Diagnose dependency/parent problems using reliable discovery (no brittle path guesses)**
   - For **missing parent / offline-only** failures: inspect the root `pom.xml` `<parent>` and every module’s `<parent>` (including any `src/it/**` project POMs); if an external parent is unavailable offline, remove/replace it and align *all* modules to an in-repo parent/version (don’t fix just one POM). When you switch parents, ensure the `<relativePath>` resolves to the in-repo parent so Maven doesn’t try to download it.
   - For **transitive dependency** failures: use `mvn dependency:tree` filtering to the problematic coordinate (add `-pl <module> -am` to focus), and when needed inspect the resolved POM in the local repository (`/home/travis/.m2/repository/.../*.pom`) to find the *true* source stanza.
   - For repository-wide searches, enumerate/target real POMs instead of typing paths from memory (`git ls-files '**/pom.xml'` or `find . -name pom.xml -not -path '*/target/*'`), then search with `rg -n` (or `grep -R --line-number`).
   - Run searches independently; avoid `cmd1 && cmd2` chains where a no-match (exit code 1) prevents subsequent searches and can hide additional occurrences.

7. **Apply fixes consistently across the whole build (multi-module + nested test projects)**
   - If a dependency/plugin configuration is present in multiple modules, either:
     - centralize the fix in the shared parent (`dependencyManagement` / `pluginManagement`), **or**
     - apply the same change to **every** module POM (and any nested invoker project POMs) that declares it.
   - Handle JDK9+ `tools.jar` / `com.sun:tools` failures end-to-end:
     - Locate the *declaring* POM (repo search for `com.sun:tools`, `tools.jar`, and/or `<systemPath>`, plus `mvn -pl <module> -am dependency:tree -Dincludes=com.sun:tools` to identify the introducer).
     - If declared in this repo, remove it from the default dependency set and make it **JDK8-and-earlier only** (e.g., move it into a profile activated for `<jdk>[1.0,1.9)</jdk>`), since JDK9+ has no `tools.jar`.
     - If it comes from a third-party dependency, prefer upgrading that dependency to a JDK9+ compatible version; otherwise exclude `com.sun:tools` where it is brought in and, if compilation/tests still need compiler classes, add the necessary JDK9+ module flags via plugin configuration (commonly `--add-modules jdk.compiler`).
     - Apply the fix anywhere it can bite: all reactor modules **and** any `src/it/**` invoker project POMs.
   - After editing, re-run the same repo-wide search to confirm there are no remaining unpatched declarations.

8. **Implement fixes via `patch_*.diff` (edit → refresh patch → reset/apply → build)**
   - Work in small batches: after each batch of edits, immediately write/refresh the required unified diff file(s) in the repo root so the changes aren’t “only in the working tree”:
     - `git status --porcelain` and `git diff --stat`
     - for each untracked new file, run `git add -N <path>` so `git diff` captures it
     - `git diff > patch_1.diff` then confirm it’s non-empty: `test -s patch_1.diff`
   - To satisfy the required workflow (**diff first, then apply**) and to ensure you’re testing exactly what you’ll submit, apply patches from a clean tree before verification builds:
     - `git reset --hard`
     - `git clean -fd -e 'patch_*.diff'`
     - `git apply patch_*.diff`
   - Re-run the Maven command used to reproduce the failure (use `-pl <module> -am` to iterate fast if needed), then run a final full-reactor `verify` once it’s green.
   - If further edits are needed, repeat the loop and overwrite `patch_1.diff` (or add `patch_2.diff`, etc.) so the patch files always match the current intended state.
   - Final sanity:
     - `ls -l patch_*.diff`
     - `test -s /home/travis/build/failed/failed_reasons.txt`
     - `git status` shows only intended project-file changes (plus untracked patch file(s)).

## Expected Result
You can (1) reproduce the original Maven failure, (2) document a clear root cause + plan in `failed_reasons.txt`, (3) implement fixes that cover all affected modules/nested test projects, (4) generate `patch_{i}.diff` files that fully capture the changes, and (5) apply those patches and pass the final Maven build.
