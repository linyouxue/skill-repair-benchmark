---
name: maven-build-lifecycle
description: Run and iterate on Maven builds in a way that quickly surfaces the *next*
  failing module/test, and ensures fixes are delivered as patch_{i}.diff files and
  applied.
---

## Steps
1. From the repo root (`/home/travis/build/failed/<repo>/<id>`), run a full build with useful diagnostics:
   - `mvn -e -DtrimStackTrace=false test` (or `verify` if that is what CI runs).
2. When the reactor fails, immediately identify the failing module and failure type:
   - **Compilation error**: note the exact missing symbol/class and the file/line.
   - **Test failure**: note the test class/method and the surefire report path under `*/target/surefire-reports/`.
3. Narrow the feedback loop to the failing module:
   - `mvn -pl :<artifactId> -am test`
   - If it’s a single test: `mvn -pl :<artifactId> -Dtest=VisibilityTest#effectiveClassVisibility test`
4. Confirm the failure by reading the exact assertion/error line from the report (don’t rely on memory):
   - `sed -n '1,200p' <module>/target/surefire-reports/*.txt` (or open the specific `...Test.txt`).
5. Inspect both:
   - the failing test source (to capture *expected* behavior), and
   - the implementation under test (to see *actual* logic).
6. Write the analysis + concrete plan to `/home/travis/build/failed/failed_reasons.txt` before changing code (so Step 2 is grounded).
7. Implement the fix, then re-run the narrowed build (Step 3) until green, then re-run the full build.
8. Produce a diff file for each logical change set:
   - `git diff > patch_2.diff` (and subsequent `patch_{i}.diff`)
   - Move it to `/home/travis/build/failed/<repo>/<id>/patch_{i}.diff`.
9. Apply the diff(s) to the working tree (ensuring Step 3 is actually completed):
   - `git apply patch_2.diff` (or `git apply /home/travis/.../patch_2.diff`)
   - Re-run the same Maven command used to validate.
## Expected Result
You can reliably (a) reproduce the failure, (b) fix it with a tight Maven command, and (c) provide and apply `patch_{i}.diff` files that make the full Maven build succeed.
