---
description: Organize mixed file sets into correct semantic folders by extracting robust signals, gating uncertainty, and verifying borderline classifications before moving files.
---

# File Organizer

## Plan the classification before moving

1. Inventory candidates (paths + extensions) and decide what evidence you will use (metadata, embedded tags, title/abstract text).
2. Prefer **high-precision cues** (explicit subject tags, embedded metadata) over weak keyword counts.
3. Add an **uncertainty gate**: when evidence is weak or conflicting, do not force a category—route to a review step.
4. Only perform bulk moves after reviewing the uncertain set and re-running extraction/classification on it.

## Extract text signals (robustly)

Extract enough text to contain title/abstract/keywords and keep the extraction method swappable.

```python
from pathlib import Path

def extract_text(path: Path) -> str:
    # Implement per-type extraction (PDF/DOCX/PPTX/TXT); return normalized text.
    text = path.read_text(errors="ignore") if path.suffix == ".txt" else ""
    return " ".join(text.split()).lower()

sample = extract_text(Path("input.ext"))
print(sample[:500])
```

Decision rule: If the extracted text is very short or obviously missing structure (e.g., empty/garbled), treat the file as **uncertain** and re-extract with a different method or larger scope.

Read references/robust-text-extraction.md when your classification depends on document content and extraction can be partial or noisy. Skip when routing is based purely on filenames or known metadata.

## Classify with an uncertainty gate

Use a scoring function, but treat uncertainty as an actionable state: **do not move** low-evidence items until they have been resolved by a second pass.

```python
from dataclasses import dataclass
from typing import Dict

@dataclass
class Decision:
    label: str | None
    scores: Dict[str, float]
    reason: str

def decide(scores: Dict[str, float], *, min_best=2.0, min_margin=1.0) -> Decision:
    best, best_s = max(scores.items(), key=lambda kv: kv[1])
    second_s = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0
    if best_s < min_best:
        return Decision(label=None, scores=scores, reason="best_below_min")
    if (best_s - second_s) < min_margin:
        return Decision(label=None, scores=scores, reason="margin_below_min")
    return Decision(label=best, scores=scores, reason="confident")

scores = {"topic_a": 0.0, "topic_b": 0.0}
print(decide(scores))
```

Decision rule: Mark the file **uncertain** (and do not move it yet) when:
- extraction is empty/failed/garbled, OR
- all/near-zero scores, ties, or top-2 margin below threshold.

Hard rule: **Moving files is conditional on `Decision.label is not None`.**

Hard rule: **Never map “uncertain” to a semantic destination folder** (including any all-zero or tie fallback). Route uncertain items to an explicit review holding area (folder or queue) and require additional evidence before any move.

Then: resolve uncertain items before moving anything in bulk.

Read references/uncertainty-gated-routing.md when any category assignment might be wrong under weak evidence (all-zero, ties, low margin, or extraction failures). Skip when the dataset has deterministic labels (e.g., explicit tags) for every file.

## Post-move verification

After moving, verify filesystem completeness *and* semantic plausibility for borderline items.

```python
from collections import Counter

def verify_assignments(assignments):
    c = Counter(a["dest"] for a in assignments)
    assert all(a["dest"] for a in assignments), "Unresolved destinations remain"
    return c
```

Decision rule: Spot-check the **lowest-margin** decisions (and any score below your best-score threshold) and require recorded high-precision evidence for each sampled file. If evidence is missing or weak, treat it as misfiled: move it back to review, re-extract, and re-classify.

Read references/post-move-borderline-audit.md when you moved many files based on heuristic scores and need to ensure semantic correctness. Skip when labels are deterministic and independently validated.

## Common Pitfalls

- Treating uncertainty as “pick a fallback folder” instead of “pause moves and resolve via second pass” (and especially using a real category as the fallback).
- Ignoring your own uncertainty diagnostics (low evidence / low margin / extraction failure) and moving files anyway.
- Extracting too little or garbled text and trusting downstream scoring anyway.
- Verifying only that “all files moved/no leftovers,” which does not detect semantic misclassification.
- Using keyword overlap as the primary signal when higher-precision cues (embedded tags/metadata) exist.
