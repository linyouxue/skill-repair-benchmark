# Robust text extraction for mixed document collections

Use this chapter when you need content-based classification and extraction can be partial, empty, or garbled across file types.

## Strategy

- Prefer extracting an identifiable snippet (title/abstract/keywords) over “first N characters”.
- Make extraction swappable: try one method, then fall back to another.
- Normalize text (whitespace collapse, lowercasing) but keep a short raw snippet for debugging.

```python
from __future__ import annotations

from pathlib import Path
from typing import Optional

import re

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def is_garbled(s: str, *, min_len: int = 200) -> bool:
    if len(s) < min_len:
        return True
    # crude signal: too many replacement chars or very low alphabetic ratio
    alpha = sum(ch.isalpha() for ch in s)
    return ("\ufffd" in s) or (alpha / max(1, len(s)) < 0.2)

def extract_text_any(path: Path) -> tuple[str, str]:
    raw = ""
    if path.suffix.lower() == ".txt":
        raw = path.read_text(errors="ignore")
    # Add per-type extraction (pdf/docx/pptx) in callers.
    norm = normalize(raw)
    return raw, norm

def extraction_ok(norm_text: str) -> bool:
    return not is_garbled(norm_text)

raw, norm = extract_text_any(Path("input.ext"))
print(extraction_ok(norm), norm[:200])
```

### Runtime branch

- If `extraction_ok(norm)` is `False`: retry using a different extractor or a broader scope (e.g., more pages, metadata fields) before classification.
- If `extraction_ok(norm)` is `True`: proceed to scoring/classification.

## Verification

For a handful of files across types:
1. Print/store a short snippet that should contain title/abstract.
2. Confirm the snippet is not empty and is human-readable.

If verification fails:
- Switch extraction method (e.g., library A → library B; CLI tool → Python library), and
- Increase scope (more pages, include metadata), then re-run extraction before any bulk classification.
