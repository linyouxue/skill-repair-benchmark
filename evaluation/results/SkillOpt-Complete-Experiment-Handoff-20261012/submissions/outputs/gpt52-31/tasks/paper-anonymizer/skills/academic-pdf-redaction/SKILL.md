---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review

Redact identifying information from academic papers for blind review.

## CRITICAL RULES



0. **End-to-end workflow is REQUIRED**
   - Create output dir: `/root/redacted`
   - Process exactly these inputs: `/root/paper1.pdf`, `/root/paper2.pdf`, `/root/paper3.pdf`
   - Write exactly these outputs: `/root/redacted/paper1.pdf`, `/root/redacted/paper2.pdf`, `/root/redacted/paper3.pdf`
   - For EACH paper: (a) inspect extracted text page-by-page, (b) collect exact full-string redaction targets **before References**, (c) apply PyMuPDF redactions, (d) scrub PDF metadata, (e) verify no sensitive strings remain in text/metadata.
1. **PRESERVE References section** - Self-citations MUST remain intact
2. **ONLY redact specific text matches** - Never redact entire pages/regions
3. **VERIFY output** - Check that 80%+ of original text remains

## Common Pitfalls to AVOID

- **Do NOT** anonymize by rasterizing pages, converting to images, or doing block/page-wide redactions. This breaks blind-review checks and often destroys searchable text.
- **Do NOT** draw black rectangles (overlays) to “hide” text—hidden text often remains extractable.
- **Do NOT** use partial-name matches (e.g., “Smith”)—this will over-redact citations in References.
- **Do NOT** redact the entire References/Bibliography section; self-citations are allowed and must remain unless there is a non-reference identity leak.

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

**IMPORTANT: Collect exact FULL strings before redacting. Do not guess; copy exact text as extracted. Use full phrases, not partial matches.**
- ✅ "John Smith" (full name)
- ❌ "Smith" (partial - would incorrectly match citations like "Smith et al." in References)

### What to scan for (page-by-page extracted text + headers/footers + footnotes)
Collect exact strings for any identity leak **before the References/Bibliography boundary**:
1. **Author list / names** (full names as printed)
2. **Affiliations**: universities, companies, departments, labs, centers, institutes, group names
3. **Emails** and **contact lines** ("correspondence to", "contact:")
4. **Homepages/URLs**: personal sites, lab sites, GitHub/org links, project pages that identify authors
5. **arXiv / preprint identifiers**: `arXiv:XXXX.XXXXX`, old-style IDs, "arXiv preprint", or preprint header blocks
6. **DOI / preprint headers** when identity-leaking (e.g., a DOI line next to author/venue info)
7. **Accepted-at / published-in / camera-ready / venue lines**: conference/workshop/journal names, proceedings info, ACM/IEEE headers, "to appear in", etc.
8. **Acknowledgements / funding**: named individuals, grants that uniquely identify the group, institutional thanks sections
9. **Author notes & footnotes**: equal contribution, corresponding author, present address, internship notes
10. **Running headers/footers** that include author names, affiliations, or venue information

### Boundary rule
- Identify the exact page where the References/Bibliography begins (e.g., first occurrence of a standalone heading like "References"/"Bibliography").
- **Do not redact inside References** unless you find a non-reference identity leak (e.g., an author email accidentally repeated there).

## PyMuPDF (fitz) - Recommended Approach



### REQUIRED: metadata scrubbing + safe save
After redacting visible text, scrub identifying PDF metadata fields that may leak authorship.
- Clear/overwrite common fields: **Author, Title, Subject, Keywords, Creator, Producer**.
- Save with garbage collection/deflate to remove leftover objects.

### REQUIRED: implementation constraints
- Use `page.search_for(exact_string)` + `page.add_redact_annot(...)` + `page.apply_redactions()`.
- **Explicitly forbidden:** drawing rectangles, rasterizing pages, or redacting blocks/whole regions.
- Before applying redactions, **deduplicate** and **log** the exact strings you will redact.

Add this after redactions and before saving:
```python
# Scrub metadata
meta = doc.metadata or {}
for k in ["author", "title", "subject", "keywords", "creator", "producer"]:
    meta[k] = ""
doc.set_metadata(meta)

# Save in a way that drops unused objects
os.makedirs(os.path.dirname(output_path), exist_ok=True)
doc.save(output_path, garbage=4, deflate=True)
```

### REQUIRED: post-save verification additions
In addition to text-retention checks, verify:
- Output exists and opens as a valid PDF
- None of the collected sensitive strings appear in extracted text of pages **before References**
- Metadata fields above are empty/non-identifying
```python
import fitz
import os

def redact_with_pymupdf(input_path: str, output_path: str, patterns: list[str]):
    """Redact specific patterns from PDF using PyMuPDF."""
    doc = fitz.open(input_path)
    original_len = sum(len(p.get_text()) for p in doc)

    # Find References page - stop redacting there
    references_page = None
    for i, page in enumerate(doc):
        if "references" in page.get_text().lower():
            references_page = i
            break

    for page_num, page in enumerate(doc):
        if references_page is not None and page_num >= references_page:
            continue  # Skip References section

        for pattern in patterns:
            # ONLY redact exact search matches
            for rect in page.search_for(pattern):
                page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()

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
    """Verify redaction didn't corrupt the PDF."""
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

    orig.close()
    redc.close()
    print("✓ Verification passed")
```
