---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the task requires producing anonymized/redacted versions of PDF documents so that authorship-revealing content is removed while the scholarly content remains readable. The binding contract for this class of task typically specifies:
- Input PDFs at known paths and output PDFs at a specified directory/filename pattern.
- Categories of information to remove: author names, affiliations, contact info, and any indirect leaks (arXiv IDs, DOIs/URLs pointing to author pages, venue/acceptance notices, funding/acknowledgement blocks, ORCID, footers/headers, watermarks, and metadata).
- A tolerance clause (e.g., self-citations may be acceptable *only if* other identifying info is already removed).

Before acting, gather:
- The exact input/output paths and filename mapping.
- The list of leakage categories the prompt enumerates (treat it as inclusive, not exhaustive).
- The tools available (e.g., `pypdf`, `pdfplumber`, `pymupdf`/`fitz`, `pikepdf`, `ocrmypdf`, `pdf2image` + OCR).
- Whether PDFs are text-based or scanned (affects whether OCR is required).
- Whether PDF metadata (Author, Title, Subject, Keywords, XMP) also needs scrubbing (assume yes for anonymization).

## Possible Failure Modes
- **Text-layer only redaction that leaves visible glyphs**: replacing text in the content stream without covering the rendered characters, so names still appear when opened in a viewer.
- **Using `pypdf` "remove text" tricks that don't actually redact**: many pypdf operations only remove text objects but leave images/vector artifacts; also they may corrupt layout.
- **Forgetting PDF metadata**: `/Author`, `/Title`, XMP metadata, and embedded document info often still contain author names after visual redaction.
- **Missing headers/footers on every page**: running-headers with author names or venue names ("Accepted at NeurIPS 2024") repeat on many pages and are easy to miss.
- **Missing the first-page author block**: title-page author list, affiliations, and email addresses are the primary leak surface.
- **Missing arXiv identifier watermark**: arXiv adds a vertical sidebar like "arXiv:2xxx.xxxxx [cs.CL]" — must be redacted.
- **Missing DOIs, URLs, ORCID iDs, GitHub/personal links** that indirectly reveal identity.
- **Missing acknowledgements/funding sections** that name authors, grants tied to labs, or advisors.
- **Not covering images/logos**: institutional logos on title page or figures.
- **Applying redaction but not "applying" it**: with PyMuPDF, `page.add_redact_annot(...)` must be followed by `page.apply_redactions()`; otherwise the annotation is decorative and text is still extractable.
- **Overzealous redaction** that removes body content, section headers, or citations unnecessarily, harming readability.
- **Wrong output path or overwriting inputs**: not creating the output directory, or writing to the input location.
- **Silent failures on one of several inputs**: processing paper1 succeeds but paper2/3 raise and are skipped without notice.
- **Copying from retrieved examples**: those examples are about encryption/data generation and are not directly applicable — do not adapt their code paths as if they were the solution.

## Possible procedures
1. **Set up output**: ensure the target output directory exists; iterate over each input PDF; map to its corresponding output filename per the contract's pattern.
2. **Detect PDF type**: try text extraction first (e.g., PyMuPDF `page.get_text("text")` / "words" / "dict"). If pages return empty text, treat as scanned and either OCR (`ocrmypdf`) first or draw opaque rectangles over identified regions using image-based detection.
3. **Identify leakage regions per page**:
   - Title page: author names line(s), affiliations, emails, ORCID, footnote symbols linking to affiliations, corresponding-author notes.
   - Sidebar/margins: arXiv identifier stamp (usually rotated text on left edge of page 1).
   - Header/footer: running titles including author names, venue notices ("To appear in ...", "Accepted at ..."), page number blocks that include author name, watermarks.
   - End-of-paper: Acknowledgements section, Author Contributions, Funding, Author Biographies, Correspondence.
   - Anywhere: email addresses (regex `\S+@\S+\.\S+`), URLs pointing to personal/lab pages, GitHub repos containing author handles, ORCID (`\d{4}-\d{4}-\d{4}-\d{3}[\dX]`), arXiv IDs (`arXiv:\d{4}\.\d{4,5}`), DOIs when tied to venue.
4. **Preferred implementation** (PyMuPDF pattern):
   - For each keyword/regex hit, use `page.search_for(text)` or iterate `page.get_text("words")` and match; collect bounding boxes.
   - Call `page.add_redact_annot(bbox, fill=(0,0,0))` (or white) for each box.
   - Call `page.apply_redactions()` — this actually removes the underlying text and draws the fill.
5. **Scrub metadata**: set document metadata fields (Author, Title if it contains names, Subject, Keywords, Creator, Producer as appropriate) to empty strings; also strip XMP metadata (`doc.set_xml_metadata("")` in PyMuPDF, or use `pikepdf` to clear `docinfo` and XMP).
6. **Self-citation policy**: leave in-text citations and reference list entries alone by default; only redact reference entries if they still expose the author's name and no other identifier has been left. The contract typically allows self-citations if other leaks are handled.
7. **Save**: write to the specified output path with `garbage=4, deflate=True` (PyMuPDF) or equivalent to ensure removed objects are not recoverable.
8. **Recovery checks**: after saving, re-open the redacted PDF, extract all text, and grep for the identifying tokens you found earlier. If any still appear, add them to the redaction pass and re-run.

Decision points:
- If text extraction is empty → OCR path or image-region redaction.
- If a name appears in ligatures or split across spans, `search_for` may miss it — fall back to word-by-word matching or use `pdfplumber` for token positions.
- If metadata cannot be edited with one library, fall back to `pikepdf`/`exiftool`.

## Verification Checklist
- [ ] Every required input file has produced exactly one output file at the exact path/pattern the contract specifies.
- [ ] Output directory was created; input files are unmodified.
- [ ] Extracting text from each output PDF yields no author names, no emails, no ORCID, no arXiv identifier, no personal/lab URLs, and no venue/acceptance strings.
- [ ] Title-page author/affiliation block is visually covered (open the PDF or render page 1 to image to confirm).
- [ ] Headers/footers and margin watermarks (including rotated arXiv stamp) are covered on all pages, not just page 1.
- [ ] Acknowledgements / funding / author-contributions sections are redacted or verified to be non-identifying.
- [ ] PDF document metadata (Info dict and XMP) contains no author-identifying values.
- [ ] Body text, figures, tables, and citations unrelated to identity are preserved and readable.
- [ ] `page.apply_redactions()` (or equivalent) was actually called; a text-extraction spot check confirms redacted strings are gone, not merely hidden.
- [ ] Self-citations, if left in, are only left in because all other identifying info has been removed — re-verify by searching for author surnames across the whole document.
- [ ] Errors on any single input do not silently skip that file; each output exists and is a valid PDF.
- [ ] No content, code, or specific values were copied from unrelated retrieved examples (those examples concern encryption/data generation and are not applicable here).
