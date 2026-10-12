# Uncertainty-gated routing for semantic file organization

Use this procedure when you are sorting many heterogeneous documents into semantic topic folders and your classifier is heuristic (keyword counts, regex matches, weak metadata) so some assignments will be ambiguous.

## Core idea

Uncertainty is a first-class outcome. If evidence is weak, **do not move the file into any real category yet**. Route it into a review queue, gather more evidence, then decide.

### Minimal artifacts

- A quarantine holding area (could be a folder path, or just a list you do not move yet)
- A `review_queue.csv` (or `.md`) that records *why* each file is unresolved and what evidence to fetch next

## Procedure

1. **Compute scores for every destination label** from the same evidence source.
2. **Compute confidence surrogates**:
   - `best_score = max(scores.values())`
   - `margin = best_score - second_best_score`
3. **Validate extraction quality** (empty/too short/garbled ⇒ uncertain).
4. **Gate**: if `best_score < min_best` OR `margin < min_margin` OR extraction failed ⇒ `label=None`.
5. **Queue** unresolved items into the review artifact; do not move.
6. **Second pass** for queued items: expand evidence, then re-score and re-gate.
7. Only once `label is not None` should the file be eligible to move.

## Runnable example (with a runtime branch)

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

@dataclass
class Decision:
    label: str | None
    best: float
    second: float
    margin: float
    reason: str

def gate(scores: Dict[str, float], text_len: int, *, min_best=2.0, min_margin=1.0) -> Decision:
    best_label, best = max(scores.items(), key=lambda kv: kv[1])
    second = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0
    margin = best - second

    if text_len < 200:
        return Decision(None, best, second, margin, "extraction_too_short")
    if best < min_best:
        return Decision(None, best, second, margin, "best_below_min")
    if margin < min_margin:
        return Decision(None, best, second, margin, "margin_below_min")
    return Decision(best_label, best, second, margin, "confident")

# --- demo data ---
items: List[Tuple[str, Dict[str, float], int]] = [
    ("a.pdf", {"topic_a": 3.0, "topic_b": 0.0}, 500),
    ("b.pdf", {"topic_a": 2.0, "topic_b": 1.6}, 800),
    ("c.pdf", {"topic_a": 5.0, "topic_b": 0.0}, 50),
]

resolved, queue = [], []
for path, scores, text_len in items:
    d = gate(scores, text_len)
    record = {"path": path, "scores": scores, "best": d.best, "margin": d.margin, "reason": d.reason}
    if d.label is None:  # branch: quarantine
        queue.append(record)
    else:               # branch: confident
        record["label"] = d.label
        resolved.append(record)

print("resolved:", resolved)
print("queue:", queue)
```

## Second-pass evidence menu (choose one or more)

- Extract more text (more pages / more slides) rather than only the first chunk.
- Use an alternate extractor (different library/CLI) when output is empty/garbled.
- Pull file metadata (Title/Subject/Keywords) if present.
- Prefer *high-precision* tags or header fields (explicit subject codes, standardized prefixes) over generic term overlap.

## Verification + corrective action

After the first pass:
- **Verify**: `len(queue) == 0` before any bulk move.
  - If not: do *not* force labels; run the second-pass evidence menu on queued items and re-run gating.

After moving:
- **Verify**: every moved file has a recorded justification (e.g., matched cues) and no file was moved with `label=None`.
  - If this fails: move the unjustified files back to quarantine, increase evidence quality (second pass), then re-run the gate.
