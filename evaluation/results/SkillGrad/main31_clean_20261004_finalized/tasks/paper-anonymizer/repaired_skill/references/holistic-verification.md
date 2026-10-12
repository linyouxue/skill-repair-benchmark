# Holistic leak verification (blind-review redaction)

Use this when the requirement is effectively “redact all information that could reveal authorship” and you must prove the written PDF is clean. This chapter gives a repeatable verification loop with multiple leak categories and prescribes what to do when a hit cannot be located by exact-string search.

## Procedure: verify → locate → redact → re-verify

1. Open the written PDF.
2. Run a detector sweep across all pages for each leak category.
3. If any detector returns hits, locate each hit on-page (rectangles or word-level), redact, save, and re-run the full detector sweep.

### Runnable skeleton

```python
import re
import fitz

LEAK_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "url": re.compile(r"https?://\S+|www\.\S+"),
    "arxiv": re.compile(r"arXiv:\s*\d{4}\.\d{4,5}|arxiv\.org/abs/\d{4}\.\d{4,5}"),
    "funding": re.compile(r"\b(NSF|DARPA|ARO|ONR|NIH|ERC)\b|\bgrant\b|\baward\b", re.I),
    "venue": re.compile(r"\b(accepted|camera[- ]ready|proceedings|workshop|conference)\b", re.I),
    "affiliation": re.compile(r"\b(university|institute|laboratory|lab|department)\b", re.I),
}


def detect_leaks(doc: fitz.Document) -> dict[str, list[tuple[int, str]]]:
    hits: dict[str, list[tuple[int, str]]] = {k: [] for k in LEAK_PATTERNS}
    for i, page in enumerate(doc):
        text = page.get_text() or ""
        for k, pat in LEAK_PATTERNS.items():
            for m in pat.finditer(text):
                hits[k].append((i, m.group(0)))
    return {k: v for k, v in hits.items() if v}


def verify_clean(path: str) -> dict[str, list[tuple[int, str]]]:
    doc = fitz.open(path)
    try:
        return detect_leaks(doc)
    finally:
        doc.close()


hits = verify_clean("output.pdf")
print("leaks:", {k: len(v) for k, v in hits.items()})
```

## Runtime branches (what to do when you find hits)

### Branch A — Exact-string location works (`search_for` returns rectangles)

For each `(page_index, surface_form)` hit, try `page.search_for(surface_form)` and redact those rectangles.

### Branch B — Hit is present in extracted text but `search_for()` returns no rectangles

Treat this as a layout/surface mismatch (line breaks, hyphenation, ligatures, superscripts). Switch to a word-level locator:
- extract `page.get_text("words")`
- find a window of consecutive words that match the hit (normalized)
- compute a union bbox and redact that rectangle

Read references/word-level-redaction.md for a runnable locator/redactor.

## Verification step (with corrective action)

After saving a redacted PDF, rerun the full `verify_clean()` detector sweep.

- If **all categories are empty**: proceed to corruption/content-retention checks.
- If **any category still has hits**: do **not** declare done; pick one remaining hit and:
  1) try Branch A for its surface form,
  2) if Branch A fails, use Branch B (word-level),
  then save and rerun verification.

If the output file cannot be opened or is missing, stop and fix the write step (path, permissions, save options), then re-run verification on the newly written file.

Decision rule: when a task explicitly names high-risk leak categories (e.g., affiliations, venue, funding), add targeted patterns for those strings/abbreviations to the detector sweep before you start iterating.
