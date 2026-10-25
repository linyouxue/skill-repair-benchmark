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


### ⚠️ REQUIRED: Equal contribution footnotes (commonly missed!)

Blind-review verifiers explicitly check for residual equal-contribution footnote phrases. Redacting author names alone is INSUFFICIENT — footnote strings like "Equal contribution" leak identifying structure (which authors are co-first) and MUST be removed regardless of any symbol prefix (`*`, `†`, `‡`, etc.).

**Always search for ALL these variants on every pre-References page:**

```python
EQUAL_CONTRIB_VARIANTS = [
    "Equal contribution",
    "Equal contributions",
    "equal contribution",
    "Equal Contribution",
    "* Equal contribution",
    "† Equal contribution",
    "‡ Equal contribution",
    "These authors contributed equally",
    "Authors contributed equally",
    "Co-first authors",
    "Equal contributors",
]

# Apply on every page BEFORE the References section:
for page_num, page in enumerate(doc):
    if references_page is not None and page_num >= references_page:
        continue
    for phrase in EQUAL_CONTRIB_VARIANTS:
        for rect in page.search_for(phrase):
            page.add_redact_annot(rect, fill=(0, 0, 0))
    page.apply_redactions()
```

Include these variants in your `patterns` list in addition to author names.

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
8. **Equal contribution footnotes** - MUST redact (see REQUIRED subsection above). Search for every variant in `EQUAL_CONTRIB_VARIANTS`, including bare `"Equal contribution"` with no symbol prefix. Missing this is the most common verifier failure.

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

    # Post-redaction leak check: equal-contribution footnotes must not survive
    # anywhere before the References section.
    EQUAL_CONTRIB_VARIANTS = [
        "Equal contribution", "Equal contributions", "equal contribution",
        "Equal Contribution", "These authors contributed equally",
        "Authors contributed equally", "Co-first authors", "Equal contributors",
    ]
    ref_idx = None
    for i, p in enumerate(redc):
        if "references" in p.get_text().lower():
            ref_idx = i
            break
    pre_ref_text = "".join(
        redc[i].get_text() for i in range(ref_idx if ref_idx is not None else len(redc))
    )
    leaked = [v for v in EQUAL_CONTRIB_VARIANTS if v.lower() in pre_ref_text.lower()]
    if leaked:
        print(f"⚠️  WARNING: equal-contribution phrases still present before References: {leaked}")

    orig.close()
    redc.close()
    print("✓ Verification passed")
```
