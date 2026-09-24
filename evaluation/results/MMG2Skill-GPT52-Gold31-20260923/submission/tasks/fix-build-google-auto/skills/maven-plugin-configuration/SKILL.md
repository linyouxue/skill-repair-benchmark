---
name: maven-plugin-configuration
description: Use Maven plugin configuration and test tooling (Surefire/Failsafe/Compiler)
  to reproduce failures precisely, inspect reports, and avoid environment/tooling
  mismatches during diagnosis.
---

## Steps
1. For unit test failures, use Surefire’s report outputs as the source of truth:
   - Find the exact failing assertion location in `<module>/target/surefire-reports/`.
   - Re-run only the failing test/method:  
     `mvn -pl :<module> -Dtest=VisibilityTest#effectiveClassVisibility test`
2. When a failure looks JDK/compiler-dependent, confirm the actual JDK Maven is using:
   - `mvn -v` and capture Java version + home in `failed_reasons.txt`.
3. If classfile inspection is needed, avoid assuming `javap` is on `PATH`:
   - Derive it from the JDK that provides `javac`:  
     `JAVAP="$(dirname "$(readlink -f "$(command -v javac)")")/javap"`  
     then run: `$JAVAP -v <class>`
4. Avoid investigation dead-ends caused by typos/mis-paths:
   - Before reading a report/file, validate it exists: `test -f path && sed -n '1,120p' path`
   - Prefer `ls <dir>` then copy/paste the filename rather than retyping.
5. If the failing behavior is due to plugin/config differences (compiler args, source/target, annotation processing), check the effective configuration:
   - `mvn -pl :<module> help:effective-pom` (and search for the relevant plugin).
6. Once fixed, validate both the narrow reproduction command and the full reactor build.
## Expected Result
Failures are reproduced with a single focused Maven command, diagnostics come from verified report paths, JDK tooling is invoked reliably, and plugin/config differences are confirmed via the effective POM rather than guesswork.
