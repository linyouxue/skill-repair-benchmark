# Hash-based deduplication workflow

Read this when you must deduplicate across one or more directories and need a safe “choose canonical, remove the rest” procedure.

## Algorithm

1. Build a table: path, size, mtime, hash.
2. Group by hash (exact duplicates).
3. For each group, pick a canonical file (rule-based), then quarantine/remove others.

## Runnable example (Python)

```python
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

@dataclass(frozen=True)
class FileRec:
    path: Path
    size: int
    mtime: float
    digest: str

def sha256(p: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()

root = Path(".")
files = [p for p in root.rglob("*") if p.is_file()]
recs: list[FileRec] = []
for p in files:
    st = p.stat()
    recs.append(FileRec(p, st.st_size, st.st_mtime, sha256(p)))

by_hash: dict[str, list[FileRec]] = {}
for r in recs:
    by_hash.setdefault(r.digest, []).append(r)

dup_groups = {h: grp for h, grp in by_hash.items() if len(grp) > 1}

quarantine = root / "_dedup_quarantine"
quarantine.mkdir(exist_ok=True)

for h, grp in dup_groups.items():
    # Branch A: choose canonical as newest mtime
    canonical = max(grp, key=lambda r: (r.mtime, -r.size))
    for r in grp:
        if r.path == canonical.path:
            continue
        target = quarantine / r.path.name
        if target.exists():
            # Branch B: name collision in quarantine -> disambiguate
            target = quarantine / f"{r.path.stem}-{r.path.stat().st_size}{r.path.suffix}"
        r.path.replace(target)

# Verification: no remaining hash groups with >1 file outside quarantine
remaining = [p for p in root.rglob("*") if p.is_file() and quarantine not in p.parents]
seen: dict[str, Path] = {}
dups_found = []
for p in remaining:
    d = sha256(p)
    if d in seen:
        dups_found.append((seen[d], p))
    else:
        seen[d] = p

if dups_found:
    # Corrective action: undo from quarantine (move back) and re-run grouping;
    # check whether some files were modified during the process.
    raise RuntimeError(f"Dedup verification failed; duplicates remain: {dups_found[:3]}")
```

## Operational notes

- Prefer quarantining over deletion; delete only after a manual spot-check.
- If hashing cost is too high: hash only candidates grouped by (size, filename) first, then hash within each candidate set.
