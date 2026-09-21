---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review



## REQUIRED END-TO-END WORKFLOW

1. Enumerate exactly `/root/paper1.pdf`, `/root/paper2.pdf`, and `/root/paper3.pdf`. Create `/root/redacted` and write exactly `/root/redacted/paper1.pdf`, `/root/redacted/paper2.pdf`, and `/root/redacted/paper3.pdf`.
2. For each input, inspect every page and every relevant layer before editing: extracted text and text blocks, positioned text, images/OCR-visible text, headers, footers, footnotes, links, annotations, widgets, bookmarks/outline entries, embedded files, document metadata, and XMP metadata. Do not assume that visible page text is the only identity-bearing content.
3. Build a document-specific inventory of full author names, affiliations, email addresses, ORCID and arXiv identifiers, DOI identifiers belonging to the manuscript, accepted/submitted/published venue statements and their variants, acknowledgements, equal-contribution statements, author-specific URLs, title-page disclosures, and equivalent identifying phrases. Include spacing, punctuation, capitalization, line-wrap, and URL variants, but use exact context-aware matches rather than isolated surnames or short fragments.
4. Determine the References boundary separately for each document by locating the actual section heading and its continuation, including cases where the heading shares a page with preceding prose. Preserve the entire References section and self-citations. Never redact a match solely because it contains a surname that also occurs in a citation; do not apply a page-wide overlay or blindly redact a whole References page.
5. Apply committed PDF redactions only to the exact identity-bearing spans before the References boundary. Redactions must remove underlying text, not merely draw black rectangles. Review matches manually or with surrounding context so that legitimate scientific text and citations remain intact.
6. Sanitize identity-bearing hidden content after visible redaction: metadata and XMP fields, producer/author/creator/title fields when identifying, bookmarks, annotations, links, widgets, embedded files, and other recoverable objects. Preserve ordinary document structure and content where it is not identity-bearing.
7. Save a clean, non-incremental output at the exact required path. Reopen each saved output and validate it before considering the task complete: it exists and is readable, has the original page count, retains normal content and at least 80% of legitimate extracted text, has no residual targeted strings in visible text or inspected objects, contains no recoverable redacted text or identity-bearing hidden artifacts, has sanitized metadata/XMP, and retains the References section and self-citations. Fail and repair any output that does not pass these checks.

Redact identifying information from academic papers for blind review.



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
7. **Acknowledgement names** - Names in "Acknowledgements" section
8. **Equal contribution footnotes** - e.g., "Equal contribution", "* Equal contribution"

## PyMuPDF (fitz) - Recommended Approach



## REQUIRED: Verification Function

**Always run this after ANY redaction to catch errors early:**
