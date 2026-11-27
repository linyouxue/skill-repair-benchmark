---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review

Redact identifying information from academic papers for blind review.

## CRITICAL RULES

1. **PRESERVE References section** - Self-citations MUST remain intact
2. **ONLY redact specific text matches** - Never redact entire pages/regions
3. **VERIFY output** - Check that 80%+ of original text remains

## Common Pitfalls to AVOID

```python
# ❌ WRONG - This removes ALL text from the page:
for block in page.get_text("blocks"):
    page.add_redact_annot(fitz.Rect(block[:4]))

# ❌ WRONG - Drawing rectangles over text:
page.draw_rect(fitz.Rect(0, 0, 600, 100), fill=(0,0,0))

# ✅ CORRECT - Only redact specific search matches:
for rect in page.search_for("John Smith"):
    page.add_redact_annot(rect)
```

## Patterns to Redact (Before References Only)

**IMPORTANT: Use FULL names/phrases, not partial matches!**
- ✅ "John Smith" (full name)
- ❌ "Smith" (partial - would incorrectly match "Smith et al." citations in References)

Before you start redacting, **collect candidate identifier strings from BOTH**:
- **Visible text** (title page/footer, first page, camera-ready footers)
- **PDF metadata** (Title/Subject/Keywords/Creator/Producer)

Then add those **exact strings** to your `patterns` list.

1. **Author names** - FULL names only (e.g., "John Smith", not just "Smith")
2. **Affiliations** - Universities, companies (e.g., "Duke University")
3. **Email addresses** - Pattern: `*@*.edu`, `*@*.com`
4. **Venue names** - Conference/workshop names (e.g., "ICML 2024", "ICML Workshop")
5. **Repository / preprint identifiers & URLs** (COMMON LEAK SOURCE)
   - arXiv IDs and variants:
     - `arXiv:2401.12345` / `arXiv:2401.12345v2`
     - `arxiv:2401.12345` (case variants)
     - old-style: `arXiv:cs/0112017`
     - URL forms: `https://arxiv.org/abs/2401.12345`, `http://arxiv.org/pdf/2401.12345.pdf`
   - DOI strings and URL forms:
     - `doi:10.1145/1234567.8901234` (case/spacing variants like `DOI: 10....`)
     - `10.1145/1234567.8901234` (bare DOI)
     - `https://doi.org/10.1145/1234567.8901234`
     - `https://dx.doi.org/10.1145/1234567.8901234`
   - Other common paper links/IDs worth scanning for (only redact if present):
     - `openreview.net/forum?id=...` / `OpenReview`
     - `ssrn.com/abstract=...` / `SSRN`
     - `hal.science/...`, `zenodo.org/record/...`, `biorxiv.org/...`, `medrxiv.org/...`
     - GitHub/project pages used as identifiers: `github.com/<org>/<repo>`, `project page:`
6. **Submission/acceptance/availability strings** (often in footers/first page)
   - e.g., "Accepted at ...", "To appear in ...", "Camera-ready", "Preprint", "Under review", "Submitted to ..."
7. **Acknowledgement names** - Names in "Acknowledgements" section
8. **Equal contribution footnotes** - e.g., "Equal contribution", "* Equal contribution"

## PyMuPDF (fitz) - Recommended Approach

```python
import fitz
import os

def _looks_like_references_heading(page: fitz.Page) -> bool:
    """Heuristic: detect a real References heading to stop redaction.

    Avoid triggering on TOC/header/footer occurrences.
    """
    # Search for the word, then apply position heuristics.
    # References headings are typically near the top half of the page.
    hits = page.search_for("References") + page.search_for("REFERENCES") + page.search_for("references")
    if not hits:
        return False

    # Keep only candidates near the top portion (typical heading area)
    top_hits = [r for r in hits if r.y0 < page.rect.height * 0.45]
    if not top_hits:
        return False

    # Confirm the page also contains citation-like patterns that usually follow references.
    # (Not perfect, but reduces false positives from headers/TOC.)
    t = page.get_text().lower()
    has_citations = ("et al." in t) or ("[1]" in t) or ("[2]" in t) or ("doi" in t) or ("arxiv" in t)
    return has_citations


def redact_with_pymupdf(input_path: str, output_path: str, patterns: list[str]):
    """Redact specific patterns from PDF using PyMuPDF."""
    doc = fitz.open(input_path)
    original_len = sum(len(p.get_text()) for p in doc)

    # Find References page - stop redacting there (robust heuristic)
    references_page = None
    for i, page in enumerate(doc):
        if _looks_like_references_heading(page):
            references_page = i
            break

    # Fallback: if uncertain, do a quick visual/spot-check rather than over-redact.
    # If your heuristic triggers on a TOC/header, you'll either redact too little or too much.
    # When in doubt, set references_page manually after inspecting page i.

    total_annots = 0

    for page_num, page in enumerate(doc):
        if references_page is not None and page_num >= references_page:
            continue  # Skip References section

        for pattern in patterns:
            # ONLY redact exact search matches
            rects = page.search_for(pattern)
            for rect in rects:
                page.add_redact_annot(rect, fill=(0, 0, 0))
            total_annots += len(rects)

        # Apply only if there is something to apply (helps avoid unintended changes)
        if page.first_annot:
            page.apply_redactions()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()

    # MUST verify after saving
    verify_redaction(input_path, output_path, expected_min_retained=0.80, min_redactions=1)
```

## REQUIRED: Verification Function

**Always run this after ANY redaction to catch errors early. Treat failures as a hard stop and iterate (tighten patterns / reduce overbroad matches) before producing final outputs.**

```python
import fitz

def verify_redaction(original_path, output_path, *, expected_min_retained=0.80, min_redactions=1):
    """Verify redaction didn't corrupt the PDF and didn't over-remove content.

    Gate conditions:
    - Page count unchanged
    - Retained text ratio >= expected_min_retained
    - Some redactions were actually applied (guards against missing identifier patterns)
    """
    orig = fitz.open(original_path)
    redc = fitz.open(output_path)

    orig_len = sum(len(p.get_text()) for p in orig)
    redc_len = sum(len(p.get_text()) for p in redc)

    # Count redaction annotations (best-effort): look for redact annots in output.
    # If your pipeline applies redactions (burns them in), annots may be gone; in that case,
    # rely on your own count during redaction (recommended) and set min_redactions accordingly.
    redact_annots = 0
    for page in redc:
        annot = page.first_annot
        while annot:
            if str(annot.type[1]).lower() == "redact":
                redact_annots += 1
            annot = annot.next

    print(f"Original: {len(orig)} pages, {orig_len} chars")
    print(f"Redacted: {len(redc)} pages, {redc_len} chars")
    if orig_len > 0:
        print(f"Retained: {redc_len/orig_len:.1%}")
    print(f"Redaction annots present (may be 0 after apply): {redact_annots}")

    # DEFENSIVE CHECKS - fail fast if something went wrong
    if len(redc) != len(orig):
        raise ValueError(f"Page count changed: {len(orig)} -> {len(redc)}")
    if redc_len < 1000:
        raise ValueError(f"PDF corrupted: only {redc_len} chars remain!")
    if orig_len > 0 and (redc_len / orig_len) < expected_min_retained:
        raise ValueError(
            f"Too much removed: kept only {redc_len/orig_len:.0%} (min {expected_min_retained:.0%}). "
            "Fix by removing overly broad patterns and ensuring you only redact exact matches on non-References pages. "
            "Also re-check your References boundary detection."
        )

    # Under-redaction guardrail: ensure you actually targeted something.
    # If redact_annots is 0 because redactions were already applied (burned in), ensure you also
    # track and assert a nonzero count in your redaction loop.
    if redact_annots == 0 and min_redactions > 0:
        print("WARNING: No redact annotations detected in output. If you used apply_redactions(), this can be normal.")
        print("         Ensure your redaction loop counted >= min_redactions matches; otherwise identifiers may remain.")

    orig.close()
    redc.close()
    print("✓ Verification passed")
```
