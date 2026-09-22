# Fixed-taxonomy completion gate (create → classify → move → verify)

Read this when the deliverable is **exactly N named folders** (often given explicitly) and the requirement includes **“no other files left out”**.

The failure mode this prevents: doing a partial pass (or a no-op) and stopping without proving that every file in scope ended up under exactly one of the target folders.

## Procedure

1. **Freeze scope root**: pick the directory whose contents must be fully organized.
2. **Create required folders first** (exact names).
3. **Inventory everything in scope** (including nested files).
4. **Classify and move** every file exactly once into exactly one target folder.
5. **Re-inventory and assert the end-state**: there are no files left outside the target folders.
6. **No-op guard:** if you executed zero mutations (no mkdir/move batch; move log empty), treat the task as incomplete even if you produced a plan.
7. If verification fails, **do not terminate**: run the repair loop (below) until it passes.

## Runnable example (Python)

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

root = Path(".")
required = ["CategoryA", "CategoryB", "CategoryC"]

def list_files(scope: Path) -> list[Path]:
    return [p for p in scope.rglob("*") if p.is_file()]

def in_targets(p: Path) -> bool:
    return any((root / name) in p.parents for name in required)

# 1) Create required folders
for name in required:
    (root / name).mkdir(parents=True, exist_ok=True)

# 2) Inventory pre-state
before = list_files(root)

# 3) Classify + move (placeholder classifier)
@dataclass
class Move:
    src: Path
    dst: Path

moves: list[Move] = []
for p in before:
    if in_targets(p):
        continue  # already placed

    # Branch A: unknown category -> default bucket (must still move somewhere)
    category = "CategoryA"

    dst = root / category / p.name
    if dst.exists():
        # Branch B: collision -> disambiguate (keep both)
        dst = root / category / f"{p.stem}-copy{p.suffix}"

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(p, dst)
    moves.append(Move(p, dst))

# 4) Verification: no leftovers outside targets
after = list_files(root)
leftovers = [p for p in after if not in_targets(p)]

# Branch C: no-op guard (common failure: ended without moving anything)
if not moves and (len(before) > 0):
    # Corrective action: confirm root is correct, then run at least one batch of moves.
    raise RuntimeError("No-op detected (0 moves). Re-check scope root and execute classify→move.")

if leftovers:
    # Corrective action: run the repair loop — reclassify/move leftovers,
    # then re-run the assertion. If leftovers are inside hidden dirs,
    # decide whether they are in-scope or should be excluded.
    raise RuntimeError(f"Completion gate failed; leftovers remain: {leftovers[:5]}")
```

## Repair loop (when verification fails)

1. Print a compact list of `leftovers` and why they weren’t moved (collision? permission? excluded patterns?).
2. **Branch: leftovers are at the root level** → classify and move them immediately.
3. **Branch: leftovers are in nested directories** → either move them too (if in-scope) or explicitly document/confirm exclusions.
4. Re-run the end-state assertion until `leftovers` is empty.

## Shell verification checklist

```bash
set -euo pipefail
root="/path/to/dir"

# 1) required folders exist (fill in exact names for the task)
for d in "CategoryA" "CategoryB" "CategoryC"; do
  test -d "$root/$d" || { echo "missing folder: $d"; exit 1; }
done

# 2) no loose files at root level
find "$root" -maxdepth 1 -type f -print

# 3) no leftovers anywhere outside targets (edit targets for the task)
find "$root" -type f \( \
  -not -path "$root/CategoryA/*" \
  -and -not -path "$root/CategoryB/*" \
  -and -not -path "$root/CategoryC/*" \
\) -print

# 4) no-op guard: ensure you actually did work
# (a) quick signal: at least one file now exists inside a target folder
find "$root/CategoryA" "$root/CategoryB" "$root/CategoryC" -type f | head
```

**If (2) or (3) prints anything:** do not stop; move those printed files into exactly one target folder (or undo/repair collisions) and re-run the checks.

**If (4) prints nothing but there were files to organize:** treat it as a no-op; re-check scope root and run the classify→move loop.
