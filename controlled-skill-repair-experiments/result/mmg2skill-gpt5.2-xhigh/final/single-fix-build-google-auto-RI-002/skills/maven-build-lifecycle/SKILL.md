---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

## Steps
1. **Locate the concrete checkout directory under `/home/travis/build/failed/**` and don’t move on until you’re in the directory that actually contains the build root `pom.xml`.** The checkout is often nested (e.g., `/home/travis/build/failed/<owner>/<repo>/<id>`), so keep drilling down. Run each `cd ... && ls -la` as a real terminal/tool invocation and wait for output (don’t end a turn with an unexecuted “I will run …”).
   - Start discovery (single tool call; short `cd ... && ls -la` is OK):
     ```bash
     cd /home/travis/build/failed && ls -la
     ```
   - Drill down one directory at a time using the same pattern (repeat until `pom.xml` is present):
     ```bash
     cd /home/travis/build/failed/<next-dir> && ls -la
     ```
   - If it’s not obvious which directory is the real checkout root, locate it directly, then `cd` to the parent and confirm:
     - Prefer a CI marker (often unique):
       ```bash
       find /home/travis/build/failed -maxdepth 6 -type f -name .travis.yml -print
       ```
     - Or find VCS roots:
       ```bash
       find /home/travis/build/failed -maxdepth 6 -type d -name .git -print
       ```
     Then:
     ```bash
     cd <parent-dir> && pwd && ls -la
     ```
     ```bash
     test -f pom.xml
     ```
     If git metadata is present, also confirm the top-level:
     ```bash
     git rev-parse --show-toplevel
     ```
     (You should see `pom.xml`, `.travis.yml`, `mvnw`, or module directories.)

2. **Create/update the required diagnosis + plan file immediately (even while still drilling down), and keep overwriting/updating it as you learn more (don’t defer to the end).**
   ```bash
   printf '%s\n' \
     "Repo: $(pwd)" \
     "Repro command: <TBD (copy exact mvn command from CI)>" \
     "Observed failure: <TBD (paste key Maven error lines)>" \
     "Root cause guess: <TBD (code vs build config)>" \
     "Plan: <TBD (files to change + why)>" \
     > /home/travis/build/failed/failed_reasons.txt
   ```
   Verify it exists and is non-empty:
   ```bash
   test -s /home/travis/build/failed/failed_reasons.txt && echo "notes ok"
   ```

3. **Read CI configuration before interpreting errors** to learn the real Maven command and JDK (then update `failed_reasons.txt` with the exact command/JDK you found):
   ```bash
   sed -n '1,220p' .travis.yml
   ```

4. **Record toolchain versions** (paste these into `failed_reasons.txt`):
   ```bash
   java -version
   ```
   ```bash
   javac -version
   ```
   ```bash
   mvn -version
   ```

5. **Match the CI JDK before patching project files.** If CI pins an older JDK and the environment provides the BugSwarm/Travis switcher:
   ```bash
   source /opt/jdk_switcher/jdk_switcher.sh
   ```
   ```bash
   jdk_switcher use <ci-jdk>
   ```
   ```bash
   export TRAVIS_JDK_VERSION=<ci-jdk>
   ```
   ```bash
   java -version
   ```
   Do not “modernize away” failures that only occur because you ran the project on a newer JDK than CI.

6. **Reproduce the failure using the CI command** (same flags/profiles, including any `-f <reactor-pom>`), then update `failed_reasons.txt` with the key error lines and whether it’s code vs build config. If you need more detailed “missing artifact/plugin” coordinates, re-run with full stack traces:
   ```bash
   mvn -B -e -X verify --fail-at-end
   ```

7. **Maven Invoker / nested test projects: when a failure happens under `target/**` (often `target/it/**`), debug there but apply fixes in the corresponding template sources (usually `src/it/**`), choosing the correct scope based on what the nested project actually inherits.**
   - Use the failing path from the Maven log (commonly shows `.../target/it/<project>/pom.xml`) to identify the `<project>` name, then locate the template directory (commonly `src/it/<project>`; confirm via the `maven-invoker-plugin` config such as `projectsDirectory` / `cloneProjectsTo` in the module POM).
   - **Do not edit** generated copies under `target/**`; edit the template `pom.xml` / `invoker.properties` (or other template build files) that produced them.
   - Choose the correct modification scope by inspecting the template project’s `<parent>` and `<relativePath>`:
     - If the template project is effectively **standalone** (no parent from your repo, or parent resolves only from repositories), make dependency/plugin fixes **inside the template** (or a parent POM within that template), because it won’t see your reactor `dependencyManagement/pluginManagement`.
     - Only fix the main reactor parent/management POM when the template project **truly inherits** from it (via a working `relativePath` in the template copy, or via a parent artifact that the build makes available to the Invoker run).
   - Distinguish **plugin resolution** failures vs normal dependency failures; standalone nested builds often need explicit plugin versions / plugin repositories in their own template.

8. **Create the required patch diff file(s), then apply them to the repo.**
   - Ensure you are at the repo root where the patch must be written:
     ```bash
     cd "$(git rev-parse --show-toplevel)"
     ```
   - Generate a unified diff from local edits (so `patch_1.diff` is created in the checkout root directory):
     ```bash
     git diff > patch_1.diff
     ```
     ```bash
     test -s patch_1.diff && echo "patch ok"
     ```
   - Prove/apply the patch artifact (separates “patch creation” from “patch application”):
     ```bash
     git checkout -- .
     ```
     ```bash
     git apply patch_1.diff
     ```
   - Verify the working tree reflects the patch:
     ```bash
     git status
     ```
     ```bash
     git diff --stat
     ```

9. **Re-run the exact CI verification command until it succeeds**, remembering `mvn verify` may run integration/Invoker steps that `mvn test` does not.

## Expected Result
- You are working inside the concrete checkout directory (contains `pom.xml` and typically `.git`).
- `/home/travis/build/failed/failed_reasons.txt` exists and is non-empty.
- `patch_1.diff` exists in the checkout root and is non-empty.
- The Maven CI command (including nested/Invoker builds when present) passes under the CI-declared JDK.
