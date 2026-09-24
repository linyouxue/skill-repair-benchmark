---
name: maven-dependency-management
description: Diagnose and fix Maven dependency/classpath problems (missing classes,
  removed JDK APIs, unwanted transitive deps) in a multi-module build.
---

## Steps
1. When compilation fails due to a missing type (e.g., `javax.annotation.Generated`), locate all occurrences first:
   - `grep -R --line-number "javax.annotation.Generated" .`
   - Record the primary failing file/line in `failed_reasons.txt`.
2. Decide the smallest, most-compatible remediation:
   - Prefer switching to a JDK-provided equivalent when appropriate (e.g., use `javax.annotation.processing.Generated` instead of `javax.annotation.Generated` to avoid relying on Java EE modules removed from newer JDKs).
   - If a replacement is not viable, add an explicit dependency in the relevant module POM (e.g., `javax.annotation:javax.annotation-api`) and confirm scope (usually `compile` for referenced production code).
3. Verify the dependency/classpath impact with Maven tooling:
   - `mvn -pl :<module> -am -DskipTests compile`
   - `mvn -pl :<module> dependency:tree -Dincludes=<groupId>:<artifactId>` when conflicts are suspected.
4. For JDK-specific artifacts like `tools.jar` (e.g., transitive `com.sun:tools` from older test utilities), prefer:
   - relying on upstream profiles guarded by file existence when available, and/or
   - excluding problematic transitive dependencies at the exact consuming dependency site (so it’s localized and doesn’t change unrelated modules).
5. After each dependency change, re-run the minimal build command that hits the failing phase (compile vs test) to confirm the error is gone.
## Expected Result
Compilation and test classpaths are correct on the current JDK, with missing-types errors resolved via either (a) a compatible type replacement or (b) an explicit, correct-scope dependency, without destabilizing other modules.
