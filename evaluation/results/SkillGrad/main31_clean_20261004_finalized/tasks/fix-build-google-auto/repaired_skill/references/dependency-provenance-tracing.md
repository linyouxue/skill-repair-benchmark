# Dependency provenance tracing (Maven)

Use this when Maven fails to resolve an artifact (missing, wrong version, unexpected scope) and you are tempted to change parents, align many versions, or edit multiple POMs.

Goal: identify the **declaring source** (which POM introduces it), its **scope** (compile/test/system), and whether it is **direct vs transitive**, so you can change the smallest correct surface.

```python
import subprocess
from dataclasses import dataclass

@dataclass
class MavenFailure:
    module: str
    ga: str  # groupId:artifactId
    expected_scope: str | None = None

def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, text=True, check=False, capture_output=True).stdout

failure = MavenFailure(module=":module", ga="group:artifact")

# Branch A: fast origin check via dependency tree (prefer for "where did this come from?")
tree = run(["mvn", "-pl", failure.module, "-Dverbose", "dependency:tree", f"-Dincludes={failure.ga}"])

# Branch B: if the tree is empty/ambiguous, search the effective POM (prefer for profiles/property expansion)
eff = run(["mvn", "-pl", failure.module, "help:effective-pom"])

origin = "dependency:tree" if failure.ga in tree else ("effective-pom" if failure.ga in eff else "unknown")
print("origin_source=", origin)

# Verification: if origin is unknown, broaden scope before editing POMs.
if origin == "unknown":
    raise SystemExit(
        "Could not find the artifact in module-scoped tree/effective POM. "
        "Next: remove -Dincludes filter, run dependency:tree for the full module, "
        "and confirm the failing module (-pl) matches the error log."
    )
```

## How to act on what you find (runtime branch)

- If the artifact is **directly declared** in the module’s POM (or its parent’s `<dependencyManagement>`), fix it **there** (version/property, scope, exclusion, or remove).
- If it is **transitive**, use an `<exclusion>` on the edge that introduces it, or align the version using `<dependencyManagement>`.
- If it is **scope=system**, treat it as a *toolchain / legacy POM* issue: prefer upgrading/replacing the declaring dependency or adjusting the build JDK/toolchain; do not assume a consumer-side exclusion will be sufficient.

## Verification step (must pass before “wide edits”)

1. Re-run the same Maven command that failed.
2. If the error is unchanged, **stop broad edits** and repeat provenance tracing with:
   - the exact failing module (`-pl`),
   - the exact groupId:artifactId filter (or no filter), and
   - `help:effective-pom` to catch profiles/property activation.

Only after you can point to the declaring source should you consider parent changes or multi-module version alignment.
