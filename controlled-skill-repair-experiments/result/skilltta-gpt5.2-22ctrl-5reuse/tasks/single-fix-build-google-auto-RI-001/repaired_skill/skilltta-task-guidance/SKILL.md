---
name: skilltta-task-guidance
---

# SkillTTA Task Guidance: Fix Java/Maven Build Errors via Repro → Diagnose → Patch → Verify

This skill guides you through reliably fixing build failures in a Java codebase under `/home/travis/build/failed/<repo>/<id>` with the required workflow:

1) reproduce and diagnose the failure,
2) write an analysis+plan to `/home/travis/build/failed/failed_reasons.txt`,
3) draft fixes as `patch_{i}.diff` (git/unified diff format),
4) apply patches and verify the build.

> Important: Follow any repository-specific conventions in `maven-build-lifecycle/SKILL.md` (toolchain selection, reproduction steps, and the exact build command to use).

---

## 0) Navigate & read the repo’s build conventions

1. Go to the repository:

```bash
cd /home/travis/build/failed/<repo>/<id>
```

2. Read the project’s build rules (this task explicitly hints they matter):

```bash
sed -n '1,200p' maven-build-lifecycle/SKILL.md
```

3. Identify the build tool and entry points:
- Maven: `pom.xml` (often multi-module)
- Gradle: `build.gradle` / `settings.gradle`

Also note:
- required JDK version (e.g., 8/11/17/21)
- the mandated command to reproduce failure (do not invent a different lifecycle if the SKILL mandates one)

---

## 1) Reproduce the failure and capture evidence

### Maven (typical)
Use the exact command specified by `maven-build-lifecycle/SKILL.md`. If none is specified, default to a standard, evidence-rich run:

```bash
mvn -e -X test | tee /tmp/build.log
```

Useful targeted re-runs:
- compile only:
  ```bash
  mvn -e -DskipTests compile | tee /tmp/build.log
  ```
- single module:
  ```bash
  mvn -pl :<artifactId> -am -e test | tee /tmp/build.log
  ```

### Extract the actionable error quickly (pattern-based log scanning)
Use grep/sed to pull the real compiler error(s) rather than the Maven “summary”:

```bash
grep -nE "\[ERROR\]|COMPILATION ERROR|Failed to execute goal|symbol:|package .* does not exist" /tmp/build.log | head -n 80
```

If tests fail:

```bash
grep -nE "Tests run:|FAILED|ERROR" -n /tmp/build.log | head -n 80
```

---

## 2) Write analysis & plan to `failed_reasons.txt`

Create `/home/travis/build/failed/failed_reasons.txt` with **concrete**, reproducible notes:

Include:
- Repo path and module (if multi-module)
- Exact command used to reproduce
- The first *root cause* error snippet (compiler/test)
- Whether it’s code vs build config
- A minimal patch plan (files to change + what to change)

Template:

```text
Repo: /home/travis/build/failed/<repo>/<id>
Build tool: Maven
Repro command: <paste exact command>
Failing module/goal: <e.g., :core / maven-compiler-plugin:compile>

Root cause (first actionable error):
<copy 10-30 lines from log, including file:line if possible>

Classification:
- [ ] Code bug (compile/runtime/test)
- [ ] Build config (pom/deps/plugins/toolchain)

Plan:
1) <file path>: <change>
2) <file path>: <change>
Verification:
- Run: <same command as repro>
```

---

## 3) Implement fixes as `patch_{i}.diff` (draft first)

### Patch drafting rules
- Put each logical fix in its own patch file when possible.
- Use **unified diff** format (compatible with `git apply`).
- Keep fixes minimal and directly tied to the error evidence.

Generate a patch from local edits:

```bash
git diff > patch_1.diff
```

Or craft one manually in standard form:

```diff
diff --git a/path/File.java b/path/File.java
index 1234567..89abcde 100644
--- a/path/File.java
+++ b/path/File.java
@@ -10,7 +10,7 @@
 ...
```

Write patches to:

```
/home/travis/build/failed/<repo>/<id>/patch_{i}.diff
```

---

## 4) Apply patches and verify

Apply patches in order:

```bash
git apply patch_1.diff
git apply patch_2.diff
```

Re-run the mandated build command (from `maven-build-lifecycle/SKILL.md` or your reproduction step):

```bash
mvn -e test
```

If still failing:
- update `failed_reasons.txt` with the new root-cause and iterate with another patch.

---

## 5) Common Maven build failure patterns & minimal fixes

### A) Compilation errors (most common)
Symptoms:
- `package ... does not exist`
- `cannot find symbol`
- method signature mismatch

Fix strategy:
- Verify correct imports/package names.
- Check if class moved/renamed; fix references.
- If dependency missing: add it to the correct `pom.xml` **in the module that compiles**.

Commands:
```bash
grep -R "<dependency>" -n pom.xml **/pom.xml
```

### B) Java version / toolchain mismatch
Symptoms:
- `invalid target release`
- `release version X not supported`

Fix strategy:
- Align `maven-compiler-plugin` `source/target` or `release` to the required JDK.
- Prefer configuring in parent POM for multi-module.

### C) Surefire test failures
Symptoms:
- `There are test failures`

Fix strategy:
- Read `target/surefire-reports/*.txt` for the real stack trace.
- Fix production code or test expectations.
- Avoid disabling tests unless the project guidelines explicitly allow it.

### D) Formatting/static analysis gates (checkstyle/spotbugs/enforcer)
Symptoms:
- `Checkstyle rule violations`
- `enforcer` version range

Fix strategy:
- Make the smallest code change to satisfy rules, or align plugin config if it’s clearly wrong/incompatible.

---

## 6) “Evidence-first” discipline (avoid guessy edits)

Before changing code/config, always:
1) reproduce,
2) extract the **first** actionable error,
3) map it to the file/line/plugin,
4) apply the smallest fix that resolves that exact issue,
5) verify with the same command.

This reduces churn and keeps patches reviewable and build-focused.
