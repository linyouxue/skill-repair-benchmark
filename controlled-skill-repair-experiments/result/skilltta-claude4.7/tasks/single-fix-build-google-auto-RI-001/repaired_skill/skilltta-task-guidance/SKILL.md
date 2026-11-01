---
name: skilltta-task-guidance
description: Temporary task guidance for diagnosing and fixing a failing Java/Maven build in /home/travis/build/failed/<repo>/<id>, producing analysis notes, diff patches, and applying them.
---

# SkillTTA Task Guidance: Fix Java Maven Build Failure

## Objective
Repair a broken Java build located at `/home/travis/build/failed/<repo>/<id>` by:
1. Diagnosing the failure (code vs. build config).
2. Writing analysis to `/home/travis/build/failed/failed_reasons.txt`.
3. Emitting standard unified diff patches as `patch_{i}.diff` in the repo root.
4. Applying the patches to the working tree.

## Location Hint Interpretation
The hint points at `maven-build-lifecycle/SKILL.md` conventions regarding:
- **Toolchain selection** (JDK version, Maven version).
- **Failure reproduction** (how to invoke the build locally).
- **Build command conventions** (e.g., `mvn -B -V -ntp ...`).
Treat these as *process* guidance — the actual bug likely lies in `pom.xml` (plugin/dep versions, Java source/target, repository config) or in a source file that no longer compiles under the configured JDK. Do not blindly trust the hint; verify by reading the repo.

## Step 1 — Reconnaissance (apply retrieval-style directory walking)
Mirror the pattern from the retrieved examples where files are enumerated and filtered by regex:
- `ls` and `find` the repo root; locate `pom.xml` (and any child modules).
- Enumerate `src/main/java` and `src/test/java` for Java sources.
- Grep for suspicious markers: `TODO`, `@Override`, deprecated APIs, `javax.*` vs `jakarta.*`, missing imports.
- Inspect `.travis.yml` / `.github/workflows/*` if present to learn the intended JDK and Maven invocation.

Reproduce the failure:
```bash
cd /home/travis/build/failed/<repo>/<id>
mvn -B -V -ntp -e clean verify 2>&1 | tee /tmp/build.log
```
If `verify` is too heavy, fall back to `compile` then `test-compile`.

## Step 2 — Classify the Error
From `/tmp/build.log`, categorize:
- **Compilation error** → fix Java source (missing symbol, type mismatch, generics, annotation processor).
- **Plugin/dep resolution error** → fix `pom.xml` (version pin, repository, relocated groupId like `com.google.auto.value`).
- **Toolchain mismatch** → align `maven.compiler.source/target` or `release` with available JDK.
- **Enforcer / checkstyle / animal-sniffer** → either fix the offending code or relax the rule if clearly misconfigured.

For a `google-auto`-flavored repo (per trial id), common culprits:
- `auto-value` / `auto-service` annotation processor not registered under `<annotationProcessorPaths>` in `maven-compiler-plugin`.
- Generated `AutoValue_*` classes missing because processor path is absent.
- Mismatch between `auto-value-annotations` (compile) and `auto-value` (processor only).

## Step 3 — Write Analysis Notes
Write `/home/travis/build/failed/failed_reasons.txt` with:
- Exact failing Maven goal and first error excerpt.
- Root cause hypothesis.
- Ordered list of file-level fixes planned.
- Validation command.

## Step 4 — Produce Diffs
For each logical change, write `patch_{i}.diff` at repo root in unified `git diff` format:
```
diff --git a/pom.xml b/pom.xml
--- a/pom.xml
+++ b/pom.xml
@@ ...
```
Keep patches minimal and focused (one concern per file). Prefer:
- Adjusting `pom.xml` plugin/dependency declarations.
- Adding missing imports or `@Override` corrections in Java sources.
- Pinning versions rather than removing dependencies.

## Step 5 — Apply Patches
```bash
cd /home/travis/build/failed/<repo>/<id>
for p in patch_*.diff; do
  git apply --whitespace=nowarn "$p" || patch -p1 < "$p"
done
```
Then re-run the build command and confirm success (or iterate).

## Transferable Patterns from Retrieved Examples
Although the retrieved examples are Python file-manipulation tasks, their reusable *patterns* are:
- **Enumerate-then-filter** (`os.listdir` + regex): mirror via `find ... | grep` to locate pom files and offending sources.
- **Guard preconditions** (`os.path.exists`, `makedirs`): before applying patches, confirm the target files exist; before writing `failed_reasons.txt`, ensure the parent dir exists.
- **Idempotent move/write**: ensure patches are safe to re-apply (check with `git apply --check` first).
- **Explicit count / status return**: after applying, report number of patches applied and the final build status.

## Deliverables Checklist
- [ ] `/home/travis/build/failed/failed_reasons.txt` populated.
- [ ] One or more `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff` files.
- [ ] Patches applied cleanly to the repo.
- [ ] Build command rerun demonstrates progress past the original error.
