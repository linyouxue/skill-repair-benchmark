---
name: skilltta-task-guidance
description: Temporary guidance for diagnosing and fixing Maven multi-module Java build failures, with emphasis on nested test projects and dependency resolution scope.
---

# SkillTTA Task Guidance: Java Maven Build Fix

## Objective
Repair build errors in a Java repository at `/home/travis/build/failed/<repo>/<id>`. Produce an analysis note, diff patches, then apply them.

## Workflow (3 Steps, Strict)

### Step 1 — Analyze
1. Discover repo root: `ls /home/travis/build/failed/` then descend to `<repo>/<id>`.
2. Inspect top-level `pom.xml` and enumerate `<modules>`. Note any **nested test projects** (e.g., `*-test`, `*-tests`, `compile-tests`, `src/it/*/pom.xml` Invoker projects, `integration-tests/`) — these often have their own reactor and dependency scopes and do **not** inherit from the outer reactor.
3. Reproduce the failure (read CI logs if present, or run `mvn -q -DskipTests install` / `mvn verify` mentally by scanning poms). Capture the first real error, not downstream cascades.
4. Classify the error:
   - **Code error**: missing symbol, API change, generics, annotation processor output.
   - **Build config error**: version mismatch, missing dependency, wrong scope (`test` vs `compile`), plugin version, Java source/target, repository URL, missing `<relativePath>`, parent version drift.
   - **Dependency resolution in nested test modules**: a nested test project (including Maven Invoker ITs under `src/it/`) may need the dependency declared in *its own* pom (not just the parent), or may need `<scope>test</scope>` lifted, or may require the module-under-test added as a dependency with correct `<version>`.
5. Write findings to `/home/travis/build/failed/failed_reasons.txt` with: root cause, affected files, minimal change plan, and risk notes.

### Step 2 — Propose Patches as Diffs
- Create `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (and `patch_2.diff`, ... if needed). Always substitute the actual `<repo>/<id>` from the task prompt; never hard-code a project name.
- Use **unified diff** format compatible with `git apply` / `patch -p1`:
  ```
  diff --git a/path/to/file b/path/to/file
  --- a/path/to/file
  +++ b/path/to/file
  @@ -L,N +L,M @@
   context
  -removed
  +added
  ```
- Keep each patch **minimal and scoped**. Prefer config fixes over code changes when both work.
- For nested test projects: modify only the nested module's pom (its own `<dependencies>` / `<dependencyManagement>` / plugin config) unless the fix truly belongs in the parent/BOM shared across modules.

### Step 3 — Apply
- `cd /home/travis/build/failed/<repo>/<id>` then `git apply --whitespace=fix patch_1.diff` (fallback: `patch -p1 < patch_1.diff`).
- Verify files changed as intended (`git diff` or `cat`).
- Confirm the repair by running **only the historical CI verify command** (as described by `maven-build-lifecycle`), under the JDK declared in `.travis.yml`. Do not invent additional test runs, benchmarks, or modernized commands — the CI command is the single finishing criterion.

## Heuristics for Common Maven Errors
| Symptom | Likely Fix |
|---|---|
| `package X does not exist` in nested test module | Add missing `<dependency>` to that module's pom (correct `groupId/artifactId/version`), scope `test` if only tests use it. |
| Invoker IT (`src/it/<name>/pom.xml`) fails: dependency not visible / wrong version | Edit the nested Invoker pom itself — add/adjust `<dependency>` or `<dependencyManagement>` there. Leave the outer reactor pom untouched unless multiple ITs need the same change. |
| `cannot find symbol` after API bump | Pin dependency to older version in `<dependencyManagement>` or update calling code. |
| `Fatal error compiling: invalid target release` | Align `maven.compiler.source/target` or `maven-compiler-plugin` release with the JDK declared by CI (do not modernize past the historical JDK). |
| `Could not resolve dependencies` | Check `<repositories>`, typos in GAV, or missing `<version>` where no BOM manages it. |
| Annotation processor output missing (e.g., AutoValue, Dagger) | Ensure `annotationProcessorPaths` configured in `maven-compiler-plugin` of the module that consumes the generated code (often a nested `*-tests` or `compile-tests` module). |
| Nested test can't see generated sources | Add `build-helper-maven-plugin` or correct `<sourceDirectory>` in the nested module. |

## Patterns Transferred from Retrieved Examples
The retrieved examples emphasize **pattern-matched traversal and conditional action** (iterate items, match by rule, act). Apply the same discipline here:
- **Iterate** modules/poms systematically (including `src/it/*/pom.xml`); don't guess.
- **Match** error messages to a known failure pattern before editing.
- **Act minimally**: one targeted change per patch file, mirroring "only move/archive files whose name matches the pattern."
- **Scope**: changes land in the smallest pom that fixes the error. Parent/BOM only when the fix is genuinely cross-module.
- **Idempotence & safety**: like `os.makedirs(..., exist_ok=True)`, ensure patches are re-appliable or clearly single-shot; never delete content you can't justify.

## Output Contract
1. `/home/travis/build/failed/failed_reasons.txt` — analysis + plan.
2. One or more `/home/travis/build/failed/<repo>/<id>/patch_*.diff` files in unified diff format.
3. Repository files updated by applying those diffs.
4. The historical CI verify command (per `maven-build-lifecycle`) succeeds end-to-end, including Invoker ITs.

## Guardrails
- Do not fabricate dependency versions; use versions already present elsewhere in the repo or in the parent/BOM.
- Do not modify unrelated modules.
- Do not assume access to any external verifier, gold answer, or prior trial.
- If multiple root causes, create separate patch files per concern.
