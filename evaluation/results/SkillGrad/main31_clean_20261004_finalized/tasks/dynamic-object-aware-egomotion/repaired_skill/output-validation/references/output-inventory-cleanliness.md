# Output inventory cleanliness (exact-manifest harnesses)

Some evaluators validate not just the presence/contents of required outputs but also the **absence of any additional files or directories touched during the run**. A common failure mode is creating debug directories (e.g., `_debug/`) or visualization images and later deleting them; the evaluation may still record the write in an output manifest/inventory, so cleanup after-the-fact does not repair the violation.

## Procedure
1) **Declare an allowlist** of deliverable paths (relative to the task workspace).
2) **Do not write** anything outside that allowlist in the workspace: no debug images, logs, caches, or intermediate NPZ/JSON.
3) If you need diagnostics, use one of:
   - in-memory summaries (counts, statistics)
   - a disabled-by-default `DEBUG=False` gate that prevents *any* file I/O when false
   - a guaranteed-ignored temp directory outside tracked outputs (e.g., OS temp) if permitted by the environment

## Runnable guard (Python)
```python
from pathlib import Path
import os

def list_paths(root: Path):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.exists())

# Runtime branch: strict manifest vs relaxed
STRICT_MANIFEST = True

root = Path(".")
allowed = {
    "interval_instructions.json",
    "masks.npz",
}

if STRICT_MANIFEST:
    found = set(list_paths(root))
    # Keep only files/dirs; ignore "." itself.
    extras = {p for p in found if p.split("/")[0] not in allowed and p not in allowed}
    if extras:
        raise RuntimeError(f"Extra artifacts in workspace: {sorted(extras)}")
else:
    # Relaxed mode: still useful to log what was created.
    print("Workspace inventory:", list_paths(root))
```

## Verification and corrective action
- **Verify**: run the guard against the workspace root just before final submission.
- **If it fails**: remove *all* debug/intermediate writes from the pipeline (do not rely on deleting afterward). Re-run from a clean workspace; then re-run the guard. If debugging is still needed, switch to in-memory stats or write outside tracked outputs.
