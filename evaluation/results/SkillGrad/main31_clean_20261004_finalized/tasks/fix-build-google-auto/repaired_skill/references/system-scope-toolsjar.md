# System-scope `tools.jar` / `com.sun:tools` failures (JDK 9+ vs legacy deps)

Use this when Maven fails with missing `com.sun:tools` / `tools.jar`, or `dependency:tree -Dverbose` shows a dependency with `scope=system` and a `systemPath` property like `${toolsjar}`.

## Why exclusions are the wrong lever

- `<exclusions>` only affect *transitive* dependencies that Maven resolves from repositories.
- A `scope=system` dependency is *declared by the artifact’s own POM* and points to a local file path; it is not a normal transitive repository edge.

So: if a third-party library declares `com.sun:tools` as `system`, adding exclusions in your consuming POM won’t make that library suddenly not require it.

## Procedure: confirm the origin, then pick the right fix

```python
import os
import subprocess
import sys

module = os.environ.get("MVN_MODULE", ".")

# Step 1: locate the declarer (effective POM and verbose dependency tree)
cmds = [
    ["mvn", "-pl", module, "-Dverbose", "dependency:tree"],
    ["mvn", "-pl", module, "help:effective-pom"],
]

for cmd in cmds:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print("$", " ".join(cmd))
    print(p.stdout[:2000])
    if p.returncode != 0:
        sys.exit(p.returncode)

# Branching is done on what you observe in the output (system scope/tools.jar vs normal transitive).
```

### Branch A — You see `com.sun:tools` with `scope=system` (often via legacy test libs)

Choose one remediation class:

1. **Upgrade/replace the declaring library** to a JDK 9+ compatible version that no longer needs tools.jar.
2. **Run that module’s tests under JDK 8** (toolchain / CI matrix change) when upgrading is not feasible.
3. **Skip/disable the specific tests/modules** that require the legacy library, only if the task/CI allows.

### Branch B — `com.sun:tools` appears as a normal transitive dependency

- Use `<exclusions>` on the direct dependency edge that pulls it in, or align versions via `<dependencyManagement>`.

## Verification (must be done)

1. Re-run the *exact* failing Maven command.
2. Confirm the original resolution error is gone.

If verification fails:

- If the same `com.sun:tools`/tools.jar error persists: re-check origin using `dependency:tree -Dverbose` and ensure you are changing the *declaring artifact* (Branch A).
- If the build proceeds but tests now fail: switch to the test-failure loop (read the Surefire/Failsafe reports) and fix the first failing test/module before making further dependency edits.
