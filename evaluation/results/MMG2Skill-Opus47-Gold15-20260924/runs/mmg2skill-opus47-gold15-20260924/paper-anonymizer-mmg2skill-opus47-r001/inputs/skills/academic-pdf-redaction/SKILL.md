---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review
Redact identifying information from academic papers for blind review.
## CRITICAL RULES
1. **PRESERVE References section** - Self-citations MUST remain intact. Prefer keeping the References pages **byte-identical** to the original (skip redaction entirely on those pages) so self-citations are provably untouched.
2. **ONLY redact specific text matches** - Never redact entire pages/regions
3. **VERIFY output** - Check page counts preserved and ≥80% text retention, then run a regex leak scan on pre-references pages.
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
1. **Author names** - FULL names only (e.g., "John Smith", not just "Smith")
2. **Affiliations** - Universities, companies (e.g., "Duke University")
3. **Email addresses** - Pattern: `*@*.edu`, `*@*.com`
4. **Venue names** - Conference/workshop names (e.g., "ICML 2024", "ICML Workshop"), including "Accepted at ..." / "To appear in ..." banners.
5. **arXiv identifiers** - Pattern: `arXiv:XXXX.XXXXX`, AND arXiv banner fragments left on the side margin such as subject tags `[eess.AS]`, `[cs.CL]` and submission dates like `30 Sep 2025`. These often appear on a rotated margin and must be searched for explicitly.
6. **DOIs** - Pattern: `10.XXXX/...`
7. **Acknowledgement content** - Names AND grant/funder identifiers (e.g., ARO/NSF/DARPA grant numbers like `W911NF-23-2-0224`). Grant numbers frequently break across lines (e.g., `W911NF` / `-23-2-` / `0224`), so also add patterns for each broken fragment and the surrounding phrase (e.g., `and ARO`, `was supported in part by`). After redaction, re-open the file and inspect residual context around funder acronyms to catch stray connective tokens like `and ARO`.
8. **Equal contribution footnotes** - e.g., "Equal contribution", "* Equal contribution"
## PyMuPDF (fitz) - Recommended Approach
```python
import fitz
import os
def redact_with_pymupdf(input_path: str, output_path: str, patterns: list[str]):
    """Redact specific patterns from PDF using PyMuPDF."""
    doc = fitz.open(input_path)
    # Find References page - stop redacting there (leave those pages byte-identical)
    references_page = None
    for i, page in enumerate(doc):
        if "references" in page.get_text().lower():
            references_page = i
            break
    for page_num, page in enumerate(doc):
        if references_page is not None and page_num >= references_page:
            continue  # Skip References section entirely -> byte-identical
        for pattern in patterns:
            for rect in page.search_for(pattern):
                page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()
    verify_redaction(input_path, output_path)
```
## REQUIRED: Verification + Leak Scan
**Always run BOTH after redaction:**
```python
import fitz, re
def verify_redaction(original_path, output_path):
    """Verify redaction didn't corrupt the PDF."""
    orig = fitz.open(original_path)
    redc = fitz.open(output_path)
    orig_len = sum(len(p.get_text()) for p in orig)
    redc_len = sum(len(p.get_text()) for p in redc)
    print(f"Original: {len(orig)} pages, {orig_len} chars")
    print(f"Redacted: {len(redc)} pages, {redc_len} chars")
    print(f"Retained: {redc_len/orig_len:.1%}")
    if len(redc) != len(orig):
        raise ValueError(f"Page count changed: {len(orig)} -> {len(redc)}")
    if redc_len < 1000:
        raise ValueError(f"PDF corrupted: only {redc_len} chars remain!")
    if redc_len < orig_len * 0.7:
        raise ValueError(f"Too much removed: kept only {redc_len/orig_len:.0%}")
    orig.close(); redc.close()
    print("✓ Verification passed")
def leak_scan(output_path, references_page, known_leaks: list[str], regexes: list[str]):
    """Scan pre-references pages for any residual identifying tokens."""
    doc = fitz.open(output_path)
    hits = []
    for i, page in enumerate(doc):
        if references_page is not None and i >= references_page:
            break
        txt = page.get_text()
        for s in known_leaks:
            if s.lower() in txt.lower():
                hits.append((i, s))
        for pat in regexes:
            for m in re.finditer(pat, txt, flags=re.IGNORECASE):
                hits.append((i, m.group(0)))
    doc.close()
    if hits:
        print("✗ LEAKS:", hits)
    else:
        print("✓ CLEAN")
    return hits
```
Run `leak_scan` with regexes covering: author-name list, affiliations, `\w+@\w+\.\w+`, `arXiv:\d{4}\.\d{4,5}`, subject tags `\[[a-z]+\.[A-Z]{2}\]`, dates like `\d{1,2}\s+[A-Z][a-z]{2}\s+20\d{2}`, DOIs `10\.\d{4,9}/`, grant IDs (e.g., `W911NF[-\d]*`, `\d{7}` NSF-style), and connective tokens near funders (`and ARO`, `and NSF`).
## Iterative fix loop
If the leak scan surfaces a residual token, inspect its **surrounding context** with `page.get_text()` slice to catch line-broken fragments (e.g., a grant ID split across three lines yielding a stray `and ARO`). Add each fragment as its own pattern, re-run, and re-scan until CLEAN for every paper.
## Preserving self-citations
Because References pages are skipped entirely, self-citations remain intact by construction. After saving, optionally confirm by comparing extracted text of References pages between original and redacted files and asserting they are byte-identical.
