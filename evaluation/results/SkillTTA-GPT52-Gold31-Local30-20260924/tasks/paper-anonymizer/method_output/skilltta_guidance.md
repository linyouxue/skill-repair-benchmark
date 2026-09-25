# SKILL.md

## When to use
Use this skill when you must **anonymize existing PDF papers** by **redacting authorship-revealing information** and saving **new redacted PDFs** to specified output paths. This includes removing/obscuring:
- **Author names**, **affiliations**, **emails**, **ORCID IDs**, **personal websites**
- **Repository/profile links** that identify authors
- **Preprint identifiers (e.g., arXiv IDs/URLs)** and other unique IDs that can reveal identity
- **Accepted venue / camera-ready / conference/journal-specific acceptance statements** if they can deanonymize

Before acting, gather evidence by:
- Inspecting each PDF’s **first page/metadata** (title block, author list, affiliations, footer headers).
- Searching within the PDF text for common leak patterns (emails, URLs, arXiv strings, “accepted at…”, institution names).
- Checking for **non-text leaks** (logos in images, scanned signatures, acknowledgments screenshots).

## Possible Failure Modes
- **Overlay instead of redaction**: drawing black rectangles without removing underlying text (text remains selectable/searchable/extractable).
- **Metadata leakage**: leaving PDF document metadata fields (Author/Creator/Producer/Subject/Keywords) intact.
- **Partial redaction**: removing author block on page 1 but missing repeats in headers/footers, acknowledgments, appendix, supplementary, or “contact” sections.
- **Identifier leakage**: missing arXiv IDs/URLs, DOI/handle links, GitHub project names, lab names, or unique URLs embedded as clickable annotations.
- **Image-based leaks**: failing to redact author names/affiliations contained in figures, screenshots, or scanned page images (no text layer to search).
- **Breaking the PDF**: producing corrupted output, losing page content, or generating an unreadable file due to incorrect saving/flattening.
- **Over-redaction that damages meaning**: removing non-identifying scientific content when only identity-related snippets are required.
- **Inconsistent outputs**: saving to wrong paths/filenames or not creating the output directory.

## Possible procedures
1. **Prepare workspace & outputs**
   - Create the required output directory (and ensure correct filenames/locations).
   - Make a safety copy of originals or work on copies if iterating.

2. **Inventory likely identity leaks per document**
   - Extract text for quick scanning (e.g., `pdftotext` or programmatic extraction) and search for patterns:
     - Emails (`@`), URLs (`http`, `www`), arXiv-like tokens, ORCID formats, “Accepted at”, “Camera-ready”, institution keywords, lab/group names.
   - Open the PDF (viewer or programmatically) and note where leaks appear:
     - Title page author block; footers/headers; acknowledgments; “code available at …”; “corresponding author”.

3. **Choose a redaction method that actually removes content**
   - Prefer a PDF redaction mechanism that **deletes underlying objects**, not just visual covering.
   - For text-based PDFs: use a library/tool that supports **true redaction annotations + applying/flattening** (ensuring removed content is not extractable).
   - For image/scanned PDFs: consider **rasterizing** affected pages/regions or applying image-level redaction, then re-embedding, since text search may not find leaks.

4. **Apply redactions**
   - For each detected leak instance:
     - Locate the exact bounding region(s) on the page.
     - Redact the region; include adjacent whitespace if needed to avoid partial characters.
   - Pay special attention to:
     - Clickable links/annotations (remove or redact them, not just the visible text).
     - Repeated headers/footers across pages.
     - “About the authors” or author contribution statements, if present.

5. **Sanitize PDF metadata and embedded properties**
   - Clear document metadata fields and, if possible, remove XMP metadata.
   - Ensure no author-identifying info remains in PDF properties.

6. **Save outputs deterministically**
   - Save each redacted PDF to the required destination path.
   - Use save options that **compact/garbage-collect** if available to reduce the chance that removed objects remain in the file.

7. **Recovery / iteration loop**
   - If verification finds remaining leaks, return to step 2 focusing on missed sections (appendix, references footers, link annotations, images).
   - If the PDF becomes unreadable, revert to originals and try a different redaction approach (e.g., rasterize only the affected pages).

## Verification Checklist
- [ ] Output directory exists and contains all required redacted PDFs with correct filenames/paths.
- [ ] Each redacted PDF opens successfully (no corruption, all pages render).
- [ ] **Search and extraction checks** on the redacted PDFs:
  - [ ] Searching for known leak patterns (emails, URLs, arXiv-like strings, “accepted at”, institution terms) returns no author-identifying hits.
  - [ ] Copy/paste or text extraction from redacted regions yields nothing meaningful (confirms not mere overlay).
- [ ] **Metadata check**: document properties/XMP do not contain author names, affiliations, or identifying keywords.
- [ ] **Annotation/link check**: hyperlinks and annotations do not expose identifying URLs/IDs.
- [ ] **Image check**: visually inspect pages containing logos/screenshots/figures for identity-bearing text not caught by text search.
- [ ] Non-identifying scientific content remains readable; only authorship-leaking content is removed.
- [ ] No reliance on retrieved examples’ concrete details (paths/IDs/values) when making decisions; decisions are derived from the target PDFs and the task contract.
