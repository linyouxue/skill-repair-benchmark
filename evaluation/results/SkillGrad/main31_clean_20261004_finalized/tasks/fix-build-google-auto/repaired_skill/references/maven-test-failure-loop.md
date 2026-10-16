# Maven test-failure loop: diagnose → patch → rerun

Use this when `mvn test` / `mvn verify` fails in Surefire or Failsafe and you need to converge quickly without spending time on noisy exploration.

## Procedure

1. **Re-run once with useful output**: run the same command with `-e` (stack traces) and optionally `-DtrimStackTrace=false`.
2. **Find the first failing module**: in a multi-module build, focus on the earliest module that fails (or use `-rf :artifactId` to resume once fixed).
3. **Read the report files** (authoritative):
   - Surefire: `target/surefire-reports/*.txt` and `*.xml`
   - Failsafe: `target/failsafe-reports/*.txt` and `*.xml`
4. **Classify the failure**:
   - **Assertion mismatch**: expected vs actual differs.
   - **Exception/timeout**: null pointer, resource missing, flaky time.
   - **Environment/JDK model difference**: reflection/annotation processing/compiler element model changed across JDKs.
5. **Apply the minimal fix** aimed at the classification.

## Runnable helper (parse failing tests)

```python
from __future__ import annotations

import glob
import pathlib

REPORT_DIRS = ["target/surefire-reports", "target/failsafe-reports"]

failing = []
for d in REPORT_DIRS:
    for p in glob.glob(str(pathlib.Path(d) / "TEST-*.xml")):
        xml = pathlib.Path(p).read_text(errors="ignore")
        if "<failure" in xml or "<error" in xml:
            failing.append(p)

if not failing:
    print("No failing TEST-*.xml found (check module selection / nonstandard report paths).")
else:
    print("Failing reports:")
    for p in failing:
        print(" -", p)
```

## Branches for fixes

### Branch A — Assertion mismatch (most common)

- Patch production code if the test is capturing a real regression.
- Patch the test if it relies on brittle ordering, message text, or implementation detail.

### Branch B — Environment/JDK model difference

- Prefer making the implementation robust (e.g., handle additional element kinds, ignore compiler-synthesized wrappers, avoid relying on `toString()` formats).
- If behavior legitimately differs by JDK, make the test conditional on an observed property (not just `java.version`) so it remains meaningful.

## Verification (must be green)

1. Re-run the *same* failing command.
2. If it still fails:
   - If the failing test set changed: repeat from step 3 focusing on the new first failure.
   - If the same test still fails: open the corresponding `*.txt` report and adjust the patch (do not continue broad greps).
