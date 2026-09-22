---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review

Redact identifying information from academic papers for blind review.

## CRITICAL RULES

1. **PRESERVE References section** - Self-citations MUST remain intact
2. **ONLY redact specific text matches** - Never redact entire pages/regions
3. **VERIFY output** - Check that 80%+ of original text remains AND that every intended pattern is actually gone

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

1. **Author names** - FULL names only (e.g., "John Smith", not just "Smith"). Also redact first-name-only occurrences that appear in acknowledgements (e.g., "We thank John for...").
2. **Affiliations** - Universities, companies (e.g., "Duke University")
3. **Email addresses** - Pattern: `*@*.edu`, `*@*.com`
4. **Venue names** - Conference/workshop names AND accompanying location/date/copyright lines (e.g., "ICML 2024", "ICML Workshop on ...", "Vancouver, Canada", "Copyright 2025 by the author(s)", "Interspeech 2024", "1-5 September 2024, Kos, Greece")
5. **arXiv identifiers** - Pattern: `arXiv:XXXX.XXXXX` AND the full vertical banner line that often appears on page 1 (e.g., `arXiv:2509.26542v1  [eess.AS]  30 Sep 2025` — redact the id, category, and date parts).
6. **DOIs** - Pattern: `10.XXXX/...`
7. **Acknowledgement content** - Names in "Acknowledgements" section AND identifying grant numbers / agencies that identify authors (e.g., "NSF 2112562", "ARO W911NF-23-2-0224", "NSFC 62072462"). Grant numbers routinely leak identity via public grant databases.
8. **Equal contribution / equal advising footnotes** — MANDATORY, and this is a common verifier trip point. `page.search_for` is case-sensitive and literal, so you MUST enumerate variants. At minimum, search for every one of:
   - `"Equal contribution"`
   - `"equal contribution"`
   - `"Equal Contribution"`
   - `"EQUAL CONTRIBUTION"`
   - `"*Equal contribution"` (asterisk-prefixed, no space)
   - `"* Equal contribution"` (asterisk-prefixed, with space)
   - `"†Equal contribution"` / `"† Equal contribution"`
   - `"Equal contributors"`, `"Equal contribution."`, `"Equal contribution,"`
   - `"These authors contributed equally"`, `"Authors contributed equally"`, `"Equally contributing authors"`
   - `"Equal advising"`, `"Equal senior authorship"`, `"Co-first authors"`, `"Co-senior authors"`
   Also grep the pre-references text with a case-insensitive regex like `r"equal(ly)?\s+(contribut|advis)"` to discover any variant you missed before finalising your pattern list.

## Recommended Discovery Workflow (before choosing patterns)

Before writing your redaction pattern list, scan each PDF once to enumerate what actually appears. This is what prevents missing variants:

```python
import fitz, re

def discover_identifiers(path, refs_page):
    doc = fitz.open(path)
    pre_refs = "".join(doc[i].get_text() for i in range(refs_page))
    doc.close()
    findings = {
        "emails":   re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", pre_refs),
        "arxiv":    re.findall(r"arXiv:\d{4}\.\d{4,5}(?:v\d+)?", pre_refs),
        "doi":      re.findall(r"10\.\d{4,9}/[^\s]+", pre_refs),
        "equal":    re.findall(r".{0,20}[Ee]qual(?:ly)?\s+(?:[Cc]ontribut|[Aa]dvis)[^\n]{0,40}", pre_refs),
        "venues":   re.findall(r"(ICML|NeurIPS|ICLR|ACL|EMNLP|CVPR|ECCV|ICCV|AAAI|Interspeech|ICASSP)[^\n]{0,60}", pre_refs),
        "grants":   re.findall(r"(NSF|ARO|NSFC|ONR|DARPA)[^\n]{0,40}", pre_refs),
        "copyright":re.findall(r"Copyright\s+\d{4}[^\n]{0,80}", pre_refs),
    }
    return findings
```

Add every discovered literal (and its obvious variants) to your `patterns` list. Do NOT rely on the examples in this file being exhaustive.

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
            # ONLY redact exact search matches. search_for is case-sensitive
            # and literal, so include case/spacing variants in `patterns`.
            for rect in page.search_for(pattern):
                page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()

    # MUST verify after saving
    verify_redaction(input_path, output_path, patterns, references_page)
```

## REQUIRED: Verification Function

**Always run this after ANY redaction. It does two independent checks:**
1. Structural check (page count, char retention).
2. **Residual-pattern check** — every literal in `patterns` must be absent from the pre-references text of the output. This is what catches missed variants like an un-redacted "Equal contribution".

```python
import fitz, re

EQUAL_CONTRIB_REGEX = re.compile(r"equal(?:ly)?\s+(?:contribut|advis)", re.IGNORECASE)
ARXIV_REGEX         = re.compile(r"arXiv:\d{4}\.\d{4,5}", re.IGNORECASE)
DOI_REGEX           = re.compile(r"\b10\.\d{4,9}/\S+")
EMAIL_REGEX         = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

def verify_redaction(original_path, output_path, patterns=None, references_page=None):
    """Verify redaction didn't corrupt the PDF and that identifiers are gone."""
    orig = fitz.open(original_path)
    redc = fitz.open(output_path)

    orig_len = sum(len(p.get_text()) for p in orig)
    redc_len = sum(len(p.get_text()) for p in redc)

    print(f"Original: {len(orig)} pages, {orig_len} chars")
    print(f"Redacted: {len(redc)} pages, {redc_len} chars")
    print(f"Retained: {redc_len/orig_len:.1%}")

    # 1) DEFENSIVE STRUCTURAL CHECKS
    if len(redc) != len(orig):
        raise ValueError(f"Page count changed: {len(orig)} -> {len(redc)}")
    if redc_len < 1000:
        raise ValueError(f"PDF corrupted: only {redc_len} chars remain!")
    if redc_len < orig_len * 0.7:
        raise ValueError(f"Too much removed: kept only {redc_len/orig_len:.0%}")

    # 2) RESIDUAL-PATTERN CHECK on pre-references pages
    if references_page is None:
        references_page = len(redc)
        for i, page in enumerate(redc):
            if "references" in page.get_text().lower():
                references_page = i
                break
    pre_refs = "".join(redc[i].get_text() for i in range(references_page))

    leaks = []
    if patterns:
        for pat in patterns:
            if pat and pat in pre_refs:
                leaks.append(f"literal not redacted: {pat!r}")

    # Category regex sweeps (catch variants the pattern list forgot)
    for name, rgx in [
        ("equal-contribution marker", EQUAL_CONTRIB_REGEX),
        ("arXiv id",                   ARXIV_REGEX),
        ("DOI",                        DOI_REGEX),
        ("email",                      EMAIL_REGEX),
    ]:
        m = rgx.search(pre_refs)
        if m:
            leaks.append(f"{name} still present: {m.group(0)!r}")

    if leaks:
        raise ValueError("Residual identifiers detected in redacted PDF:\n  - " +
                         "\n  - ".join(leaks))

    orig.close()
    redc.close()
    print("✓ Verification passed")
```

If `verify_redaction` raises, extend your `patterns` list with the reported variant and re-run redaction. Do not declare the task done until this function passes for every output PDF.
