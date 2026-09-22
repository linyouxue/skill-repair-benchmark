# Execution log + undo workflow (many moves/renames)

Use this when you will perform lots of filesystem mutations and need a reversible, auditable process.

## Procedure

1. Create a machine-readable move log (TSV or JSONL) with `src`, `dst`, and an action type.
2. Prefer a staging run: small batch first, verify, then scale.
3. After each batch, verify that:
   - destination files exist
   - file counts roughly match expectation
   - spot-check a few important files open correctly

## Runnable example (Python)

```python
from __future__ import annotations

import csv
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Move:
    src: Path
    dst: Path

root = Path(".")
log_path = root / "moves.tsv"
ops = [
    Move(root / "in" / "a.txt", root / "out" / "a.txt"),
    Move(root / "in" / "b.txt", root / "out" / "b.txt"),
]

log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("w", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["src", "dst"])
    for m in ops:
        w.writerow([str(m.src), str(m.dst)])

for m in ops:
    m.dst.parent.mkdir(parents=True, exist_ok=True)
    if m.dst.exists():
        # Branch: collision -> keep existing, route to a staging decision later
        continue
    if not m.src.exists():
        # Branch: missing source -> stop early; fix inventory/selection first
        raise FileNotFoundError(m.src)
    shutil.move(m.src, m.dst)

# Verification: every logged dst exists
with log_path.open(newline="") as f:
    r = csv.DictReader(f, delimiter="\t")
    missing = [row for row in r if not Path(row["dst"]).exists()]

if missing:
    # Corrective action: run undo for this batch and re-plan collisions/missing sources
    raise RuntimeError(f"Post-move verification failed; undo batch. Missing: {missing[:3]}")
```

## Undo (reverse the log)

```python
import csv
from pathlib import Path
import shutil

log_path = Path("moves.tsv")

with log_path.open(newline="") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))

# Reverse order to handle nested moves
for row in reversed(rows):
    src = Path(row["dst"])
    dst = Path(row["src"])
    if not src.exists():
        # Branch: already missing -> skip and report
        continue
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, dst)

# Verification: original sources restored
not_restored = [row for row in rows if not Path(row["src"]).exists()]
if not_restored:
    # Corrective action: inspect collisions and restore from backups if available
    raise RuntimeError(f"Undo incomplete; inspect collisions/backups: {not_restored[:3]}")
```
