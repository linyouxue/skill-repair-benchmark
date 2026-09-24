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

1. **Author names** - FULL names only (e.g., "John Smith", not just "Smith")
2. **Affiliations** - Universities, companies (e.g., "Duke University")
3. **Email addresses** - Pattern: `*@*.edu`, `*@*.com`
4. **Venue names** - Conference/workshop names (e.g., "ICML 2024", "ICML Workshop")
5. **arXiv identifiers** - Pattern: `arXiv:XXXX.XXXXX`
6. **DOIs** - Pattern: `10.XXXX/...`
7. **Acknowledgement names** - Names in "Acknowledgements" section (also grant numbers / funder codes that appear alongside them and can identify authors, e.g., "W911NF-...", "NSF 1234567")
8. **Equal contribution footnotes** - canonical fixed-string variants that MUST be probed for every paper, regardless of whether they were noticed on first scan:
   - `Equal contribution`
   - `* Equal contribution`
   - `*Equal contribution`
   - `Equal Contribution`
   - `Equal contributions`
   - `†Equal contribution` / `‡Equal contribution` (and other footnote-marker variants)

### MANDATORY: per-document category coverage checklist

Before invoking the redactor for a paper, walk the 8 categories above in order and, for each one, EITHER:

- add at least one concrete search string to that paper's `patterns` list, OR
- record a short justification that the category is genuinely not present in the pre-References pages of this document (e.g., "no DOI printed on first page").

Categories that are usually fixed phrases rather than document-specific tokens (notably #8 Equal contribution footnotes, and generic markers like `arXiv:`, `@`, `doi.org/`) SHOULD be added by default to every paper's `patterns` list, because they are cheap to search and easy to overlook during ad-hoc reading of page 1. A category must never be silently skipped just because no instance was noticed while browsing.

## PyMuPDF (fitz) - Recommended Approach

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

**Always run this after ANY redaction to catch errors early.**

Verification MUST do two independent things:

1. Structural / retention checks (page count, character retention thresholds).
2. **Category-taxonomy probes** derived directly from the 8 categories in "Patterns to Redact", executed on the pre-References pages of the redacted PDF. These probes are intentionally independent of whatever `patterns` list the planner happened to build for this paper, so that a category dropped during planning surfaces here as a leak instead of a false "clean" pass.

Only when both the structural checks pass AND every category probe returns no hit on the pre-References pages may the run be declared clean. If any probe fires, treat it as a real leak: extend that paper's `patterns` list (or record a justified exemption for a genuine false-positive, e.g., a body-text mention that is not authorship-revealing) and re-run redaction before finishing.

```python
import fitz
import re

# One lightweight probe per skill-listed category. These probes should be
# broad enough to catch a category that was entirely forgotten during planning,
# but they are NOT the redaction patterns themselves.
CATEGORY_PROBES = {
    "emails (#3)":                 re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "arxiv ids (#5)":              re.compile(r"arXiv:\s*\d{4}\.\d{4,5}", re.IGNORECASE),
    "dois (#6)":                   re.compile(r"\b10\.\d{4,9}/\S+"),
    "equal-contribution (#8)":     re.compile(r"equal\s+contribution", re.IGNORECASE),
}

def _pre_refs_text(doc):
    refs = None
    for i, page in enumerate(doc):
        if "references" in page.get_text().lower():
            refs = i
            break
    end = refs if refs is not None else len(doc)
    return "".join(doc[i].get_text() for i in range(end))

def verify_redaction(original_path, output_path):
    """Verify redaction didn't corrupt the PDF and that no skill-listed
    category was silently skipped."""
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

    # CATEGORY PROBES - one per skill-listed leakage category.
    # These run on the redacted, pre-References text only.
    pre_refs = _pre_refs_text(redc)
    leaks = {}
    for label, probe in CATEGORY_PROBES.items():
        hits = probe.findall(pre_refs)
        if hits:
            leaks[label] = hits[:5]
    if leaks:
        raise ValueError(
            "Category-probe leaks in pre-References pages; extend patterns "
            f"and re-redact: {leaks}"
        )

    orig.close()
    redc.close()
    print("✓ Verification passed")
```

Note: the probes above cover the categories that have canonical fixed-string / regex forms (#3, #5, #6, #8). Categories #1, #2, #4, #7 are inherently document-specific (proper nouns), so their coverage is enforced by the per-document checklist under "Patterns to Redact" rather than by a generic probe here.
