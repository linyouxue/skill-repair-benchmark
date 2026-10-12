# Post-move borderline audit (semantic verification)

Use this when you already moved many files based on heuristic classification and need a systematic way to catch misfiles that “all files moved” checks cannot detect.

## Goal

Find and correct the most likely misclassifications by auditing the **lowest-confidence assignments across all destination folders**.

## Procedure

1. Ensure you saved per-file decision details during classification (path, chosen label, scores, best, second, margin, extraction length, and key matched cues).
2. Sort decisions by increasing confidence (typically `margin`, then `best`).
3. Sample bottom-*k* globally (not per-folder spot checks only).
4. For each sampled file, re-open / re-extract more evidence and confirm the destination is justifiable.
5. If not justifiable, move the file back to quarantine/review, then re-classify.

## Runnable example (with a runtime branch)

```python
from __future__ import annotations

from typing import Dict, List

Dec = Dict[str, object]

def bottom_k(decisions: List[Dec], k: int) -> List[Dec]:
    # lower margin + lower best score are more suspicious
    return sorted(decisions, key=lambda d: (float(d["margin"]), float(d["best"])))[:k]

# demo decisions
decisions: List[Dec] = [
    {"path": "a.pdf", "label": "topic_a", "best": 5.0, "margin": 4.0, "cues": ["explicit_tag"]},
    {"path": "b.pdf", "label": "topic_b", "best": 2.2, "margin": 0.2, "cues": ["weak_keyword"]},
    {"path": "c.pdf", "label": "topic_a", "best": 2.0, "margin": 0.0, "cues": []},
]

suspects = bottom_k(decisions, k=2)
for d in suspects:
    cues = list(d.get("cues", []))

    # Branch: missing/weak justification -> send to review
    if len(cues) == 0 or float(d["margin"]) < 0.5:
        d["action"] = "move_back_to_quarantine_and_reextract"
    else:
        d["action"] = "keep_as_is"

print(suspects)
```

## Verification + corrective action

- **Verify**: Every suspect decision has a human-justifiable reason (high-precision cue or strong margin).
  - If any suspect lacks justification: move it back to quarantine, increase evidence quality (more pages/alternate extractor/metadata), then re-run classification.

- **Verify**: After corrections, recompute the bottom-*k* list.
  - If the new bottom-*k* is still dominated by weak/empty cues: tighten thresholds (`min_best`, `min_margin`) and/or improve extraction before any further moves.
