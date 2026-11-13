---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

## Steps
1. **Locate the real checkout workspace** under `/home/travis/build/failed/**` and confirm you’re at the Maven+git root. Execute each command as an actual terminal/tool invocation (don’t just print it) and only continue after you’ve seen its output.
   - Start discovery (single tool call; short `cd ... && ls -la` is OK):
     ```bash
     cd /home/travis/build/failed && ls -la
     ```
   - Drill down with `ls -la` (e.g., `cd /home/travis/build/failed/<owner-or-repo> && ls -la`) until you reach the final workspace directory that contains `pom.xml` and usually a `.git` directory/file.
   - If you’re unsure where the checkout root is, find it directly:
     ```bash
     find /home/travis/build/failed -maxdepth 5 -type d -name .git -print
     ```
     Then `cd` to the parent directory of the `.git` hit and confirm:
     ```bash
     cd <parent-of-.git> && pwd && ls -la
     ```
     ```bash
     test -f pom.xml && git rev-parse --show-toplevel
     ```
     (You should see `pom.xml`, `.travis.yml`, `mvnw`, or module directories.)

2. **Write/update the required diagnosis + plan file immediately** (keep overwriting/updating it as you learn more; don’t defer to the end):
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

6. **Reproduce the failure using the CI command** (same flags/profiles, including any `-f <reactor-pom>`), then update `failed_reasons.txt` with the key error lines and whether it’s code vs build config. If you need clearer “missing artifact/plugin” coordinates, also try:
   ```bash
   mvn -o -B -e verify --fail-at-end
   ```

7. **Maven Invoker / nested test projects: fix dependency resolution in the template sources, not `target/**`.**
   - If the failure is in a nested build (Invoker often runs under `target/it/**` or `target/**`), map the failing nested directory back to its **source template** (commonly `src/it/**`, sometimes `src/test/resources/**`) and edit that template’s `pom.xml` / `invoker.properties`, not generated copies under `target/**`.
   - Choose the correct modification scope by checking the nested project’s `<parent>` chain:
     - If the nested project **does not inherit** from your reactor/parent POM, fixes must be made **inside the nested template** (or a parent POM within that template), because it won’t see your reactor `dependencyManagement/pluginManagement`.
     - If it **does inherit** from a repository parent POM, fix the parent so the nested project picks up the change naturally.
   - Distinguish **plugin resolution** failures vs normal dependency failures; nested builds may need their own plugin versions/repositories when they don’t inherit yours.

8. **Create the required patch diff file(s), then apply them to the repo.**
   - Ensure you are at the repo root where the patch must be written:
     ```bash
     cd "$(git rev-parse --show-toplevel)"
     ```
   - Generate a unified diff from local edits (run in the repo root so the patch lands at `/home/travis/build/failed/<repo>/<id>/patch_1.diff`):
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
- `patch_1.diff` exists in the repo root and is non-empty.
- The Maven CI command (including nested/Invoker builds when present) passes under the CI-declared JDK.
