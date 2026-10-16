---
name: maven-build-lifecycle
description: Iterate on Maven builds by rerunning the same target command until it is green, and only export patches from real working-tree edits.
---

# Maven Build Lifecycle

Master Maven's build lifecycle including phases, goals, profiles, and build customization for efficient Java project builds.

## Verify-first workflow (close the loop)

1. Run the exact CI/target command (same `-f`, profiles, and flags) and treat the first failure as your current gate.
2. **Gate on provenance before wide edits:** before changing parents, reactor versions, or many POMs, locate the *declaring* source and scope of the failing artifact in the failing module (effective POM / verbose dependency tree).
3. Fix only the earliest failing module/phase first (dependency resolution → compile → tests → packaging), then re-run the same command immediately.
4. Treat every "new" failure after a fix as expected: record it, fix it, and keep looping until the full command succeeds.
5. Do not leave changes in a "draft" state: always apply edits to the working tree and re-run the target command; avoid reasoning about un-applied diffs.
6. Do not hand-author diff hunks: edit files, then generate the patch with `git diff` (or `git format-patch`) and validate it applies.
7. When tests fail, read the Surefire/Failsafe report files under `target/*-reports/` for the authoritative stack trace and assertion diff.

```bash
mvn -B -e verify
# before large-scale POM edits, confirm where the failing artifact is declared
mvn -pl <module> -Dverbose dependency:tree -Dincludes=<groupId:artifactId>
# make edits in the working tree
git diff > patch_1.diff
# gate submission on the patch applying cleanly
git apply --check patch_1.diff
```

Decision rule: if you cannot show a final successful run of the exact target command *and* a patch that passes `git apply --check`, assume the task is still failing and continue iterating.

Read references/dependency-provenance-tracing.md when a build fails on a missing/undesired artifact and you are about to change parents, align many versions, or edit multiple POMs.
Skip when you already know the exact declaring POM line (e.g., a direct dependency in the current module) and only need to apply a small local edit.

Read references/patch-export-and-apply-check.md when you are preparing `patch_1.diff` or see `git apply` errors like “corrupt patch” or “patch does not apply”.
Skip when you are not required to output a patch file (you can commit directly).

Read references/maven-test-failure-loop.md when `mvn ... test/verify` fails in Surefire/Failsafe and you need a tight diagnose→patch→rerun loop.
Skip when you already have a single known failing test with a clear minimal fix.

Read references/jdk9-element-enclosing-walk.md when upgrading to JDK 9+ reveals incorrect symbol/name/visibility logic that walks `Element.getEnclosingElement()`.
Skip when failures are confined to dependency resolution or plugin configuration (no Java element-model traversal involved).

## Default Lifecycle Phases

### Complete Phase Order

```
1.  validate      - Validate project structure
2.  initialize    - Initialize build state
3.  generate-sources
4.  process-sources
5.  generate-resources
6.  process-resources - Copy resources to output
7.  compile       - Compile source code
8.  process-classes
9.  generate-test-sources
10. process-test-sources
11. generate-test-resources
12. process-test-resources
13. test-compile  - Compile test sources
14. process-test-classes
15. test          - Run unit tests
16. prepare-package
17. package       - Create JAR/WAR
18. pre-integration-test
19. integration-test - Run integration tests
20. post-integration-test
21. verify        - Run verification checks
22. install       - Install to local repo
23. deploy        - Deploy to remote repo
```

## Common Pitfalls

1. **Stopping early** - A build that "gets further" is still failing; iterate until the exact target command is green.
2. **Unapplied/draft changes** - Reasoning about a fix without applying it and re-running the target command leaves the true failure unknown.
3. **Hand-authored patches** - Manually editing diff hunks leads to “corrupt patch” / “patch does not apply”; export patches from real working-tree edits and gate on `git apply --check`.
4. **Multi-POM edits without origin check** - Editing many module POMs before confirming the *declaring* source (effective POM / verbose dependency tree) leads to cargo-cult fixes.
