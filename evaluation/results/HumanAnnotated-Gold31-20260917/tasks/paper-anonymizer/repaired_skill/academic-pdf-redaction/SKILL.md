---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review

Redact identifying information from academic papers for blind review.

## CRITICAL RULES

1. **PRESERVE cited reference entries** - Self-citations MUST remain intact, but a page that contains References may still have current-manuscript headers, footers, or venue boilerplate that must be redacted
2. **ONLY redact exact candidate glyphs** - Never redact entire pages, regions, lines, or extractor spans unless every glyph inside that rectangle is explicitly authorized for removal
3. **VERIFY every removal** - A retained-character percentage is diagnostic only; delivery requires a fail-closed pre/post diff proving that no non-whitespace text outside approved redaction rectangles disappeared
4. **NEVER SHRINK THE CANDIDATE LEDGER** - Build one immutable, all-page ledger from the original PDF before applying any redaction. Every retry or regenerated output must reuse every ledger item; it may refine a bounding box or change a classification only with a recorded reason, but it must never replace the ledger with a document-, page-, section-, or pattern-specific subset

## Mandatory candidate ledger and region-level redaction gate

Before applying any redaction, divide the manuscript into these evidence zones:

1. document metadata;
2. title/front matter, author footnotes, running headers, and running footers;
3. acknowledgements, funding statements, and venue/proceedings boilerplate;
4. main scientific content;
5. individual cited-reference entries.

### Required all-page discovery pass

Do not begin redaction after inspecting only metadata, the first page, or identifier regexes. First extract text with page numbers and coordinates from every page and print a compact page-by-page coverage table. For every page, explicitly account for each mandatory class: (a) person names; (b) institutional affiliations and locations; (c) contact and correspondence details; (d) authorship or contribution disclosures; (e) acknowledgement and funding text; and (f) venue, preprint, DOI, URL, and other current-manuscript identifiers. Each page/category cell must contain ledger item IDs or the explicit status `none-after-inspection`; a missing cell is `unresolved` and blocks redaction and delivery.

Candidate sources are a union, never alternative fallbacks: document metadata, title/front matter, author/correspondence/contribution footnotes, acknowledgement and funding sections, recurring headers and footers, and all-page pattern scans must all run whether metadata is present or absent. Locate acknowledgement, funding, author-contribution, and related section ranges from their headings through the next peer-level heading, then inspect every person and organization phrase inside them. Inspect title-page bottom footnotes even when they fall outside the normal front-matter vertical band. Contribution disclosures such as "equal contribution", "contributed equally", or equivalent wording are candidates in their own right even after the associated author names have been removed.

Keep the pre-redaction ledger immutable across debugging retries. A retry made to fix one rectangle must start from the full original ledger and assert that all original ledger IDs are still present before overwriting an output. Never rebuild one paper from a shortened detector list merely because another candidate class already passed an earlier check.

Scan metadata and every page for candidate identifying evidence, including proper names, affiliations, contact details, grants, venue/proceedings marks, arXiv identifiers, DOI values, and URLs. Record **every discovered candidate** in a ledger with at least:

- literal occurrence text and, optionally, its normalized value;
- evidence category;
- page and an exact candidate-only bounding box;
- ownership: `current-manuscript`, `cited-work`, or `unresolved`;
- action: `redact` or `preserve`;
- post-redaction verification result.

Reference protection is semantic and region-level, not page-level. Preserve author names and identifiers that belong to cited-reference entries. On the first References page, content above the References heading is outside the protected entry region; on every References page, running headers, footers, margins, and venue or publisher boilerplate are also outside it. Do not skip an entire page merely because a References heading appears on it: current-manuscript running headers, footers, copyright lines, venue boilerplate, arXiv identifiers, DOI values, or URLs outside the cited-entry region must still be classified and, when identifying, redacted on every occurrence. Treat separate occurrences of the same normalized value as separate ledger rows because they may have different ownership and actions. If ownership is uncertain, inspect the surrounding line, page geometry, repeated placement, and nearby section heading; do not silently drop the candidate.

The cited-reference region begins at the actual References/Bibliography heading and continues across following pages until either the document ends or an unmistakable new top-level non-reference section begins. A continuation page remains part of the cited-reference region even when it does not repeat the heading. Bibliographies may be numbered, author-year, paragraph-style, or mixed. **Never infer that References ended from citation-number syntax, line density, a low-density streak, column changes, or page layout.** When no explicit next top-level section exists, keep subsequent body-area text protected as reference-entry content while still classifying repeated headers, footers, margins, and boilerplate independently.

Each ledger rectangle must tightly enclose only the literal candidate occurrence authorized for removal. PDF extractors often combine a target with innocent surrounding words in one span; the parent span or line rectangle is therefore not an acceptable redaction rectangle. Resolve an exact occurrence with `page.search_for(literal)`, character-level quads/boxes from `rawdict`, or an equivalently tight clipped rectangle. If an exact candidate-only rectangle cannot be established, leave the item unresolved and do not redact or finish.

A pattern hit creates a candidate, not a redaction action. Do not infer ownership from identifier type or page number alone. When a regex matches only part of an extractor span, materialize the exact `match.group(0)` text and derive boxes for that literal from character boxes or occurrence-disambiguated exact search results. A global identifier deletion regex is not a valid plan because it can erase cited works, and using the containing span bbox for a substring match is also invalid. Likewise, scanning identifiers without reconciling every match into the ledger is incomplete.

Completion is blocked until all of the following checks pass:

- every page/category cell in the coverage table is explicitly reconciled; metadata-only, first-page-only, or regex-only discovery is incomplete;
- every regeneration contains the complete immutable pre-redaction ledger; no candidate ID or mandatory category was dropped while debugging another item;
- the discovered-candidate set equals the classified-candidate set and no item remains `unresolved`;
- every `redact` ledger item is absent at all recorded occurrences in the output;
- every `preserve` ledger item remains present in its cited-reference entry;
- for every page, a pre/post word-token diff finds no removed token outside the exact authorized `redact` rectangles;
- the output opens successfully and preserves the original page count.
- an independent post-redaction leakage pass re-extracts every output page and repeats all mandatory category scans, rather than checking only literals already present in the ledger; every remaining hit is classified, and any unchecked category or remaining current-manuscript candidate blocks delivery.

Print or otherwise inspect the final ledger reconciliation before delivery. If any candidate is missing a decision or any check fails, revise the ledger or redaction rectangles and regenerate the PDF.

## Common Pitfalls to AVOID

```python
# ❌ WRONG - This removes ALL text from the page:
for block in page.get_text("blocks"):
    page.add_redact_annot(fitz.Rect(block[:4]))

# ❌ WRONG - Drawing rectangles over text:
page.draw_rect(fitz.Rect(0, 0, 600, 100), fill=(0,0,0))

# ❌ WRONG - Guessing that unnumbered or low-density bibliography pages
# are no longer part of References:
if low_reference_density(page):
    references_ended = True

# ❌ WRONG - Redacting an extractor span that also contains innocent text:
page.add_redact_annot(fitz.Rect(parent_span["bbox"]))

# ✅ CORRECT - Only redact specific search matches:
for rect in page.search_for("John Smith"):
    page.add_redact_annot(rect)
```

## Candidate Types to Inventory and Classify

This is not a blanket redaction list and is not limited by page number. Decide each occurrence using the ownership, surrounding context, and region rules above.

**IMPORTANT: Use FULL names/phrases, not partial matches!**
- ✅ "John Smith" (full name)
- ❌ "Smith" (partial - would incorrectly match "Smith et al." citations in References)

1. **Author names** - FULL names only (e.g., "John Smith", not just "Smith")
2. **Affiliations** - Universities, institutes, laboratories, departments, and companies (e.g., "Example University")
3. **Email addresses** - Pattern: `*@*.edu`, `*@*.com`
4. **Venue names** - Conference/workshop names (e.g., "ICML 2024", "ICML Workshop")
5. **Current-manuscript arXiv identifiers outside cited-reference entries** - Pattern: `arXiv:XXXX.XXXXX`
6. **Current-manuscript DOIs outside cited-reference entries** - Pattern: `10.XXXX/...`
7. **Acknowledgement names** - Names in "Acknowledgements" section
8. **Equal contribution footnotes** - e.g., "Equal contribution", "* Equal contribution"

## PyMuPDF (fitz) - Recommended Approach

```python
import fitz
import os

def redact_with_pymupdf(input_path: str, output_path: str, ledger: list[dict]):
    """Redact only ledger-approved occurrences using PyMuPDF."""
    doc = fitz.open(input_path)
    original_len = sum(len(p.get_text()) for p in doc)

    # Never skip a whole References page. The ledger must already distinguish
    # cited-entry occurrences from current-manuscript headers/footers.
    for item in ledger:
        if item["action"] != "redact":
            continue
        if item.get("bbox_scope") != "exact-candidate":
            raise ValueError("Refusing a non-exact redaction rectangle")
        page = doc[item["page"]]
        rect = fitz.Rect(item["bbox"])
        page.add_redact_annot(rect, fill=(0, 0, 0))

    for page in doc:
        page.apply_redactions()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()

    # MUST verify after saving
    verify_redaction(input_path, output_path, ledger)
```

## REQUIRED: Verification Function

**Always run this after ANY redaction to catch errors early:**

```python
from collections import Counter, defaultdict
import fitz

def _glyphs(page):
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                for char in span["chars"]:
                    rect = fitz.Rect(char["bbox"])
                    yield char["c"], rect, fitz.Point(
                        (rect.x0 + rect.x1) / 2,
                        (rect.y0 + rect.y1) / 2,
                    )

def _spatial_glyph_counter(page, excluded_rectangles=()):
    glyphs = Counter()
    for char, rect, center in _glyphs(page):
        # PDF redaction engines may absorb adjacent whitespace without removing
        # semantic content. Compare substantive glyphs; word-token checks cover
        # textual preservation separately.
        if char.isspace():
            continue
        if any(center in excluded for excluded in excluded_rectangles):
            continue
        key = (
            char.casefold(),
            round(rect.x0, 1), round(rect.y0, 1),
            round(rect.x1, 1), round(rect.y1, 1),
        )
        glyphs[key] += 1
    return glyphs

def verify_redaction(original_path, output_path, ledger):
    """Fail if any non-whitespace glyph outside approved rectangles disappeared."""
    orig = fitz.open(original_path)
    redc = fitz.open(output_path)

    if len(redc) != len(orig):
        raise ValueError(f"Page count changed: {len(orig)} -> {len(redc)}")

    approved = defaultdict(list)
    for item in ledger:
        if item["action"] == "redact":
            if item.get("bbox_scope") != "exact-candidate":
                raise ValueError(f"Non-exact bbox in ledger: {item}")
            rect = fitz.Rect(item["bbox"])
            approved[item["page"]].append(rect)
            if redc[item["page"]].get_textbox(rect).strip():
                raise ValueError(f"Approved occurrence still present: {item}")
        elif item["action"] == "preserve":
            if not redc[item["page"]].search_for(item["literal"]):
                raise ValueError(f"Protected occurrence disappeared: {item}")
        else:
            raise ValueError(f"Unresolved ledger action: {item}")
        item["post_redaction_verification"] = "passed"

    for page_index in range(len(orig)):
        protected_original = _spatial_glyph_counter(
            orig[page_index], approved[page_index]
        )
        output_glyphs = _spatial_glyph_counter(redc[page_index])
        missing = protected_original - output_glyphs
        if missing:
            raise ValueError(
                f"Page {page_index + 1} has unauthorized removals: "
                f"{list(missing.elements())[:20]}"
            )

    orig.close()
    redc.close()
    print("✓ Verification passed: every removed word was ledger-authorized")
```
