---
name: skilltta-task-guidance
---

# SkillTTA Task Guidance: Fixing Java/Maven Build Errors (with nested test projects)

This guidance helps you systematically diagnose and fix Maven/Java build failures in a repository located at:

`/home/travis/build/failed/<repo>/<id>`

You must:
1) Write analysis + plan to `/home/travis/build/failed/failed_reasons.txt`.
2) Draft fixes as `patch_{i}.diff` files in standard `git diff` format.
3) Apply those patches to the repository.

The location hint points to **`maven-build-lifecycle/SKILL.md`**, specifically around **nested test project dependency resolution and modification scope**. Treat that as a likely source of failure.

---

## A. High-signal workflow (repeatable)

### 1) Reproduce the failure and capture the *real* error
From repo root:

```bash
cd /home/travis/build/failed/<repo>/<id>
# Run with stacktraces and verbose error output
mvn -e -X test 2>&1 | tee /tmp/mvn.log
```

Then extract the important lines:

```bash
grep -nE "\[ERROR\]|Failed to execute goal|Could not resolve|Non-resolvable parent POM|The POM for|Compilation failure" /tmp/mvn.log | head -200
```

This mirrors a reliable “search for ERROR occurrences” pattern: instead of reading everything, **regex/grep the log** to quickly isolate root cause.

### 2) Identify whether it’s code vs build configuration
Classify quickly:

- **Dependency / POM / plugin issues** (most common):
  - `Could not resolve dependencies`
  - `Non-resolvable parent POM`
  - `The POM for ... is missing`
  - `Plugin ... could not be resolved`
  - Often fixed in `pom.xml`, parent/child linkage, repositories, versions.

- **Compilation errors**:
  - `cannot find symbol`, type mismatch, missing imports
  - Fix in `src/main/java` or `src/test/java`.

- **Test failures**:
  - Surefire/Failsafe output shows assertion errors
  - Fix tests or test setup (or adjust plugin config only if justified).

Write this classification + the *exact* failing module and goal into `failed_reasons.txt`.

---

## B. Maven multi-module + nested test projects: what to check

The hint emphasizes **nested test projects**. Common Maven patterns that break builds:

### 1) A nested test project is unintentionally part of the reactor
Sometimes a sample/integration-test project under e.g. `src/test/resources/...` or `maven-build-lifecycle/...` is:
- incorrectly included in `<modules>`
- or has its own `pom.xml` that Maven tries to treat as a module

Fix options (choose minimal scope):
- Remove it from the parent `<modules>` if it’s not meant to build.
- Add `<skipTests>` or plugin config **only inside that nested project** if it’s supposed to exist but not run.
- Mark it with `<packaging>pom</packaging>` (only if appropriate) or ensure it has valid parent linkage.

### 2) Dependency resolution inside nested test projects
Nested test projects often fail because their `pom.xml`:
- references a parent that isn’t resolvable (`<relativePath>` wrong/missing)
- uses `${project.version}` but isn’t in the same reactor
- depends on the root artifact without using a correct version

Fix patterns:
- If the nested project should inherit the repo’s parent, ensure:
  - `parent` coordinates match
  - `<relativePath>` points correctly (or remove it to let Maven resolve from reactor)

Example fix direction:
- Adjust `<relativePath>../../pom.xml</relativePath>` to the correct number of `../`.
- If the nested project must depend on a module in the same build, depend on the correct `groupId:artifactId:${project.version}` and ensure it’s in the same reactor.

### 3) Modification scope (important)
Make the smallest change that fixes the build:
- Prefer editing `pom.xml` for dependency/plugin resolution issues.
- Avoid broad refactors.
- Limit changes to the module(s) indicated by the Maven error.

When writing `failed_reasons.txt`, explicitly state “I will only change module X / file Y because error Z indicates …”.

---

## C. Writing `/home/travis/build/failed/failed_reasons.txt`

Include:
1) The exact failing Maven goal + module (copy from log).
2) The minimal root cause.
3) The plan: list files to change and what to change.

Template:

```
Build fails at: <module> / goal <...>
Key error: <paste exact lines>
Classification: dependency-resolution | plugin | compile | test
Root cause hypothesis: <one paragraph>
Plan (minimal scope):
  1) Edit <file> to <change>
  2) Add/adjust <version>/<relativePath>/<dependencyManagement> ...
Validation: mvn -q test (or mvn -pl <module> -am test)
```

---

## D. Producing patch diffs (`patch_{i}.diff`)

Create diffs in standard `git diff` format.

Workflow:

```bash
# Make edits
$EDITOR path/to/file

# Review
git diff

# Save into required location
git diff > /home/travis/build/failed/<repo>/<id>/patch_1.diff
```

If multiple independent fixes, split into multiple patch files (`patch_1.diff`, `patch_2.diff`).

---

## E. Applying patches

Apply and re-run Maven:

```bash
cd /home/travis/build/failed/<repo>/<id>
git apply patch_1.diff
mvn -q test
```

If the build still fails, repeat: re-check `/tmp/mvn.log`, refine minimal changes, produce a new patch.

---

## F. Quick triage commands (useful shortcuts)

Search for nested POMs (often reveals unintended modules):

```bash
find . -name pom.xml -print
```

Locate `<modules>` blocks:

```bash
grep -RIn "<modules>" -n .
```

Find references to a problematic artifact/version:

```bash
grep -RIn "<artifactId>THE_ID</artifactId>" -n .
grep -RIn "relativePath" -n .
```

If logs are huge, use focused grep (pattern-based extraction):

```bash
grep -nE "\[ERROR\]|Non-resolvable parent POM|Could not resolve|Compilation failure" -n /tmp/mvn.log | head -120
```

---

## G. Common Maven fixes that are low-risk

- Add explicit plugin versions (avoids old defaults): surefire, compiler plugin.
- Align Java source/target in `maven-compiler-plugin` if error indicates unsupported release.
- Fix parent `<relativePath>` for modules.
- Ensure test-only dependencies use `<scope>test</scope>`.
- Remove accidental repositories pointing to blocked/unavailable URLs (prefer Maven Central) **only if resolution fails due to that repo**.

---

## Done criteria

You are finished when:
- `mvn test` (or the project’s standard build command) completes successfully.
- Patches are saved as required and applied.
- `failed_reasons.txt` clearly documents cause + fix plan.
