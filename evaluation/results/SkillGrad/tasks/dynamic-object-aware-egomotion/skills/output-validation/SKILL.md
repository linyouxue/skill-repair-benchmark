---
name: output-validation
description: "Validate that required on-disk artifacts exist, reload correctly, and meet format invariants before termination."
---

# When to use
- Right before you terminate (and also as a recovery step if a prior run produced missing/empty outputs).

## Deliverables gate (hard stop)
1) **Declare deliverables (absolute paths + conventions)**: print the exact required artifact paths and key naming rules you will satisfy.
2) **Preflight the filesystem**: ensure the parent directory exists and is writable; avoid doing expensive work if you cannot write.
3) **Run the full pipeline that produces those artifacts** (do not skip): sampling/indexing → estimation → mask building → writers.
4) **Write required artifacts unconditionally** (even if outputs are trivial):
   - JSON: interval instructions.
   - NPZ: per-frame masks (CSR encoding) + global `shape`.
5) **Re-open from disk and validate** (existence + loadability + key coverage + invariants).
6) **Termination interlock**: immediately before any `end_turn`, assert the required absolute paths exist and are loadable; if not, run `references/deliverables-gate.md` end-to-end and re-check until it passes.

Read references/deliverables-gate.md when the harness expects specific on-disk paths or a prior run produced missing/empty outputs. Skip when the caller writes/validates artifacts outside your control.

## Checks (fast, local)
- **Existence**: required absolute paths exist on disk (not just in memory).
- **Key format**: every interval key is `"{start}->{end}"` (integers only).
- **Coverage**: keys cover the intended sampled frames and are within video bounds.
- **Frame count**: NPZ contains exactly one CSR triplet per sampled frame.
- **CSR integrity**: `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices within `[0,W)`.
- **Value validity**: JSON values are non-empty string lists; labels are in the allowed set.

# Code sketch
```python
import json, os
import numpy as np

# Paths should be task-provided; validate existence/loadability before exit.
assert os.path.exists(instructions_path)
assert os.path.exists(masks_path)

with open(instructions_path, "r") as f:
    instructions = json.load(f)
npz = np.load(masks_path)

# Basic structural checks
assert "shape" in npz
for k, v in instructions.items():
    s, e = k.split("->")
    assert s.isdigit() and e.isdigit()
    assert isinstance(v, list) and len(v) > 0
```

## Common Pitfalls
- Terminating before running the pipeline and deliverables gate (no artifacts on disk).
- Passing in-memory checks but never writing artifacts to disk (evaluation only sees files).
- Writing NPZ without all per-frame CSR keys (`data/indices/indptr`) for every sampled frame.
- Interval keys that look human-readable but violate the strict `start->end` machine format.
