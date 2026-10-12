# Scope policy when preserving References

Use this chapter when you must preserve the References section’s citations/prose but still remove specific identifier classes (e.g., arXiv IDs/URLs) everywhere.

## Two-tier policy

- **Tier 1 (pre-References):** redact identity-bearing prose such as author names, affiliations, emails, author homepages/handles, venue/acceptance strings, and acknowledgement names.
- **Tier 2 (global):** redact globally-disallowed identifier classes on **all pages**, including inside References (commonly arXiv IDs/URLs).

## Procedure (with branches)

```python
import re
import fitz

REF_RE = re.compile(r"\breferences\b", re.I)


def find_references_start(doc: fitz.Document) -> int | None:
    for i, page in enumerate(doc):
        if REF_RE.search(page.get_text() or ""):
            return i
    return None
```

- **Branch A (References start found):**
  1) Apply Tier 1 redactions only on pages `< ref_start`.
  2) Apply Tier 2 redactions on all pages.

- **Branch B (References not detected):**
  1) Do not assume “no references”; apply Tier 2 globally.
  2) Apply Tier 1 conservatively (e.g., first N pages) only if instructed; otherwise require user guidance.

## Verification (required)

After saving, re-scan for Tier 2 detectors (e.g., arXiv URL/ID regex). If any Tier 2 hits remain, do **not** declare success: add those exact surface forms (and variants) to the redaction set and re-run.

If Tier 1 redactions are suspected of harming citations, check that common citation patterns remain (e.g., “et al.”, bracketed references) and rollback any overly broad token (use full names/phrases only).
