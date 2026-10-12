---
description: Normalize numbered choice labels by stripping ordinal prefixes while preserving semantic content; verify against examples and keep normalization minimal.
---

# Normalize choice labels

## Trigger

Read this when choice lines are numbered (e.g., `1. ...`, `2) ...`) or bulleted and you need to set `Edge.text`.

## Procedure

1. **Strip only the presentational prefix** (leading number + delimiter).
2. **Preserve semantic content** (tags, bracketed markers, punctuation after the label).
3. **Apply normalization consistently** for every choice edge.

```python
import re

_PREFIX = re.compile(r"^\s*(?:\d+\s*[-\.)]|[-*•])\s+")

def normalize_choice_label(s: str) -> str:
    return _PREFIX.sub("", s).strip()

# Example usage
edge_text = normalize_choice_label(raw_choice_text)
```

## Runtime branch

- **If stripping removes meaningful content** (e.g., the label genuinely starts with a number as part of the meaning):
  - keep the original string and skip normalization for that one edge,
  - but record the exception rationale (so you don’t inconsistently normalize similar items).

## Verification

- Spot-check a few normalized labels:
  - no leading ordinals/bullets remain,
  - semantic tags (e.g., `[Lie]`) remain.

If verification fails: tighten the regex to match only the specific delimiter form present in the input, and re-run normalization on all edges.
