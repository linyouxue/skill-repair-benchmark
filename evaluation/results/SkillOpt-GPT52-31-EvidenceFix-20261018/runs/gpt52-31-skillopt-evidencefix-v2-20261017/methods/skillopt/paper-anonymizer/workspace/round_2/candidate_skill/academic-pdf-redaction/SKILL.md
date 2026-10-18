---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review

Redact identifying information from academic papers for blind review.

## CRITICAL RULES

1. **HARD STOP at References/Bibliography** — Locate the first page containing a standalone heading like "References" or "Bibliography" and **prohibit any redactions on that page and all following pages**. Implementation hint: compute `stop_page` once, then only iterate pages `0..stop_page-1`.


   - Treat the first page whose heading line is exactly/primarily "References", "Bibliography", or similar as immutable citation territory.
   - Do not redact anything on `stop_page` or later pages, even if those pages contain author names, arXiv IDs, DOI strings, URLs, or affiliations inside citations.
   - Avoid substring-only detection such as `if "references" in text`; instead inspect line-level headings to prevent false positives from prose like "details are in the references".
   - Compute `stop_page` once before building redaction patterns, and enforce it consistently for search, annotation, and verification passes.
2. **ONLY redact specific text matches** — Never redact entire pages/regions; never run global regex redaction across the whole PDF.
3. **PRESERVE References content verbatim** — Do not redact arXiv/DOI/URL strings that belong to cited works in References/Bibliography.
4. **VERIFY output** — Check that 80%+ of original text remains and that only allowed items were removed.

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

## Patterns to Redact (STRICTLY before References/Bibliography)

**IMPORTANT: Use FULL names/phrases, not partial matches!**
- ✅ "John Smith" (full name)
- ❌ "Smith" (partial - would incorrectly match "Smith et al." citations)

1. **Author names** — FULL names only (e.g., "John Smith", not just "Smith")
2. **Affiliations** — Universities, companies (e.g., "Duke University")
3. **Email addresses** — redact exact email strings found in text (avoid wildcard/global regex across entire PDF)
4. **Venue names / acceptance strings** — only when they refer to this paper (front matter, headers/footers, camera-ready/accepted statements)
5. **arXiv/URL/DOI identifiers (tight scope)**
   - ✅ Redact **only** when they clearly identify the *current paper* (common locations: first page footer/header, title block, author footnotes, “Our paper is on arXiv …”, project page links).
   - ❌ Do **NOT** blanket-redact every `arXiv:` / `10.` / `https://` match. This causes over-redaction in citations and unrelated links.
   - ❌ Never redact arXiv/DOI/URLs that are part of cited works in **References/Bibliography** (and you should be skipping those pages entirely).
6. **Acknowledgements / Thanks section personal names** — see required procedure below


8. **Pre-reference metadata and footnotes** — explicitly scan title blocks, headers/footers, copyright notices, correspondence notes, equal-contribution notes, acceptance/camera-ready text, acknowledgements, and author footnotes before `stop_page`.
   - Redact exact identifiers that deanonymize the current paper, including full personal names (e.g. "Shengyuan Xu", "Pengcheng Zhu"), paper-specific arXiv IDs (e.g. "arXiv:2509.26542"), and publication DOIs tied to this paper (e.g. "10.21437/Interspeech.2024-33").
   - Use exact full-string matches only. Never remove generic tokens like `arXiv`, `10.`, domains, surnames alone, or institution fragments globally.
7. **Equal contribution footnotes** — e.g., "Equal contribution", "* Equal contribution"

## PyMuPDF (fitz) - Recommended Approach


### REQUIRED: Section-aware boundarying + Acknowledgements name handling

**Boundarying (mandatory):**
- Detect the first true References/Bibliography heading page and set `stop_page`.
- Only scan/redact pages `< stop_page`.
- Heading detection hint: prefer line/heading match over substring anywhere in the page to avoid stopping early on sentences like "in the references".

**Acknowledgements + footnotes procedure (mandatory):**
1. On all pages `< stop_page`, inspect acknowledgement sections, title-page footnotes, correspondence notes, equal-contribution notes, and metadata/footer blocks.
2. For acknowledgement spans ("Acknowledgements"/"Acknowledgments"/"Thanks"), locate text from the heading to the next major heading.
3. Extract candidate **full names** from those spans (e.g., 2–4 Capitalized words) and manually/heuristically filter to likely people.
4. Add those exact full-name strings to `patterns` and redact exact matches only.
5. Separately collect exact paper-identifying strings appearing before References, including:
   - paper-specific arXiv IDs (`arXiv:2509.26542`)
   - publication DOIs for the current paper (`10.21437/Interspeech.2024-33`)
   - project/repository URLs tied to the paper
   - acceptance or venue statements for this submission
6. Never generalize these into global regex removals. For example:
   - ✅ redact `arXiv:2509.26542` when it appears in a preprint footer before References
   - ✅ redact `10.21437/Interspeech.2024-33` when it identifies the current paper before References
   - ❌ do not redact unrelated citation entries such as `arXiv:2503.04721` or DOI/URL strings inside the References pages
   - ❌ do not redact surnames alone or every `https://` occurrence


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


    # Identifier recall checks (pre-References only)
    orig_text = "\n".join(p.get_text() for p in orig[:max(len(orig)-1, 1)])
    redc_text = "\n".join(p.get_text() for p in redc[:max(len(redc)-1, 1)])

    # Replace with the exact identifiers collected for the current paper.
    targeted_identifiers = [
        # e.g. "Shengyuan Xu",
        # e.g. "Pengcheng Zhu",
        # e.g. "arXiv:2509.26542",
        # e.g. "10.21437/Interspeech.2024-33",
    ]

    for ident in targeted_identifiers:
        if ident in orig_text and ident in redc_text:
            raise ValueError(f"Identifier still present after redaction: {ident}")

    orig.close()
    redc.close()
    print("✓ Verification passed")
```


## REQUIRED: Final Validation Checklist (before submitting)

- [ ] **No redactions at/after References/Bibliography**: confirm `stop_page` found and pages `>= stop_page` are untouched.
- [ ] **Acknowledgements sanitized** (pre-References): no remaining thanked individual full names, emails, affiliations, or lab names.
- [ ] **Identifiers sanitized (tight scope)**: arXiv/DOI/URL that identify *this paper* are removed from front matter/headers/footers; cited-work identifiers in References remain unchanged.
- [ ] **Retention**: retained text is **≥ 80%** and there are no large unexpected deletions (spot-check by diffing extracted text and sampling missing words).
