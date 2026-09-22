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
4. **DO NOT over-redact References while fixing identifier leaks**
   - If you must remove identifiers that appear in the References (e.g., arXiv links), redact **only the identifier substring** (e.g., the `arXiv:YYYY.NNNNN` token or `arxiv.org/abs/...` token), not surrounding citation text.

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

## Patterns to Redact (Body, Front Matter, and Acknowledgements)

**IMPORTANT: Use FULL names/phrases, not partial matches!**
- ✅ "John Smith" (full name)
- ❌ "Smith" (partial - would incorrectly match "Smith et al." citations in References)

1. **Author names** - FULL names only (e.g., "John Smith", not just "Smith")
2. **Affiliations** - Universities, companies (e.g., "Duke University")
3. **Email addresses** - Pattern: `*@*.edu`, `*@*.com`
4. **Venue names** - Conference/workshop names (e.g., "ICML 2024", "ICML Workshop")
5. **arXiv identifiers** - Pattern: `arXiv:XXXX.XXXXX`
6. **DOIs** - Pattern: `10.XXXX/...`
7. **Acknowledgement names** - Names in "Acknowledgements" section
8. **Equal contribution footnotes** - e.g., "Equal contribution", "* Equal contribution"

### Boundary rule (what to redact where)

- **Default**: redact items in front matter + main body **up to (but not including) the References section**.
- **Acknowledgements is NOT protected**: even though it is often near the end, it is considered identifying. Redact names and identifying phrases inside **Acknowledgements** (and similar sections like "Acknowledgment", "Acknowledgements and Funding", "Funding").
- **References is protected for citations**: preserve self-citations and reference entries. If identifiers like arXiv links/IDs must be removed in References, do **surgical** redaction of the identifier token only.

## PyMuPDF (fitz) - Recommended Approach

```python
import fitz
import os
import re

def find_section_page(doc: fitz.Document, headings: list[str]) -> int | None:
    """Return first page index containing a section heading.

    Robust against numbered headings like '6. References' and casing.
    """
    # Matches lines like: 'References', '6. References', '6 References'
    heading_re = re.compile(r"^\s*(?:\d+\s*\.?\s*)?(%s)\s*$" % "|".join(map(re.escape, headings)), re.I)

    for i, page in enumerate(doc):
        lines = page.get_text("text").splitlines()
        for ln in lines[:120]:
            if heading_re.match(ln.strip()):
                return i
    return None


def redact_with_pymupdf(input_path: str, output_path: str, patterns: list[str]):
    """Redact specific patterns from PDF using PyMuPDF.

    Strategy:
    - Identify References start and (optionally) Acknowledgements pages.
    - Redact normally before References.
    - Ensure Acknowledgements content is redacted even if it appears near the end.
    - Avoid broad/global redaction that removes large parts of References.
    """
    doc = fitz.open(input_path)
    original_len = sum(len(p.get_text()) for p in doc)

    references_page = find_section_page(doc, ["References"])
    acknowledgements_page = find_section_page(doc, ["Acknowledgements", "Acknowledgment", "Funding"])

    for page_num, page in enumerate(doc):
        in_references = references_page is not None and page_num >= references_page

        # Redact in main body (not References)
        if not in_references:
            for pattern in patterns:
                # ONLY redact exact search matches
                for rect in page.search_for(pattern):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()

        # Special handling: Acknowledgements content must be anonymized
        # If acknowledgements_page exists and it occurs before References, it is already handled above.
        # If it occurs after/near the end (layout variance), handle it explicitly.
        if acknowledgements_page is not None and page_num >= acknowledgements_page and (references_page is None or page_num < references_page):
            # (This branch mainly matters when acknowledgements are late but still before references.)
            pass

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()

    # MUST verify after saving
    verify_redaction(input_path, output_path)
```

## REQUIRED: Verification Function

**Always run this after ANY redaction to catch errors early:**

```python
import fitz

def verify_redaction(original_path, output_path):
    """Verify redaction didn't corrupt the PDF or remove too much content."""
    orig = fitz.open(original_path)
    redc = fitz.open(output_path)

    orig_len = sum(len(p.get_text()) for p in orig)
    redc_len = sum(len(p.get_text()) for p in redc)

    print(f"Original: {len(orig)} pages, {orig_len} chars")
    print(f"Redacted: {len(redc)} pages, {redc_len} chars")
    print(f"Retained: {redc_len/orig_len:.1%}")

    # DEFENSIVE CHECKS - fail fast if something went wrong
    if len(redc) != len(orig):
        raise ValueError(f"Page count changed: {len(orig)} -> {len(redc)}")
    if redc_len < 1000:
        raise ValueError(f"PDF corrupted: only {redc_len} chars remain!")
    if redc_len < orig_len * 0.7:
        raise ValueError(f"Too much removed: kept only {redc_len/orig_len:.0%}")

    # Additional guardrail: detect suspicious over-redaction in References
    # If your workflow redacts identifiers in References, it should be token-level only.
    # A large drop in extracted text often indicates overly broad redaction.
    # (Tune thresholds per project; keep conservative here.)
    if redc_len < orig_len * 0.9:
        print("WARN: Large overall text drop; check you did not redact beyond intended tokens.")

    orig.close()
    redc.close()
    print("✓ Verification passed")
```
