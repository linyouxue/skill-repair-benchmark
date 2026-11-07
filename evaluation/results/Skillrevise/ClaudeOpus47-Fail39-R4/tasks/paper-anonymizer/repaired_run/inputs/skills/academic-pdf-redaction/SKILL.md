# Academic PDF Redaction for Blind Review

## Purpose
Anonymize an academic PDF so that no author-identifying content remains in text, footers, or metadata, while preserving document structure and readability. Self-citations in References may stay only after all other identifying info has been verifiably removed.

## When to Use
Trigger when the task is to produce a de-identified version of an academic PDF (single or batch) for blind review, and the verifier judges anonymization completeness rather than textual edit distance. Do not use for layout changes, OCR, or redaction of non-identifying content.

## Procedure
- Validate inputs: confirm input PDF path exists, output directory is writable, and `fitz` (PyMuPDF) imports. If `fitz` is unavailable, stop and report the missing dependency; do not fall back to drawing rectangles over text.
- Discover identifiers (do not hard-code):
- Parse the first 1-2 pages to extract an author set and affiliation set (lines above the abstract, footnote markers, "Equal contribution" blocks). Print the extracted sets.
- Build regex classes and compile them once: emails (`[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}`), arXiv IDs (`arXiv:\d{4}\.\d{4,5}(v\d+)?`), arxiv.org URLs (`https?://arxiv\.org/\S+`), DOIs (`10\.\d{4,9}/\S+`), grant/funding IDs (`\b[A-Z]{2,}-?\d{3,}\b` filtered by context words like "grant", "award", "NSF", "NIH"), venue/copyright footers (lines matching conference acronym + 4-digit year, or starting with "Copyright", "Preprint", "To appear"), and repo URLs containing author handles (`https?://(github|gitlab|huggingface)\.com/\S+`).
- Run every regex over every page's text and print per-class hit counts. Non-zero counts for emails or arXiv on an academic paper is the expected observable; zero everywhere is a signal that extraction failed - re-check text extraction before proceeding.
- Redact in a single pass per page using `page.search_for(match)` for each discovered literal; call `page.add_redact_annot(rect)` then `page.apply_redactions()`. For strings that `search_for` cannot locate, retry with whitespace-normalized and hyphen-variant forms before giving up; log unresolved strings.
- Handle References conditionally:
- Locate a References/Bibliography heading via case-insensitive text search. If found, first redact only non-author identifiers (arXiv, DOI, URLs, emails) in References, leaving author surnames in self-citations.
- If References heading cannot be located, treat the whole document uniformly (no preservation zone).
- After the Verify step below, if any residual author-identifying leak is detected anywhere, escalate: also redact author surnames and affiliations inside References and re-verify.
- Scrub PDF metadata: set `doc.set_metadata({})` (or overwrite author/title/subject/keywords/producer/creator to empty strings) before saving.
- Save to the output path (create parent dir if missing), then Verify:
- Reopen the saved PDF. Re-run the same regex discovery and author/affiliation substring scan. Expected evidence: zero hits for emails, arXiv, DOIs, author-handle repo URLs, author names, and affiliations in the non-References zone (and in References too after escalation).
- Assert page count unchanged and total text length is non-trivial (sanity check against corruption, not an acceptance threshold).
- Inspect `doc.metadata` and confirm identifying fields are empty.
- If any residual hit remains, loop back to the Redact step with the newly discovered strings; cap at a small iteration bound and report remaining leaks if unresolved.

## Constraints / Pitfalls
- Never redact entire blocks, pages, or draw filled rectangles over text; only redact exact rects returned by `search_for`.
- Do not hard-code author names, affiliations, or venue strings in the skill; derive them from the current document each run.
- Treat "preserve References" as conditional, not absolute: self-citations may remain only when the Verify step confirms the rest of the document is clean.
- Do not rely on text-retention percentage as an acceptance signal; the contract is anonymization completeness verified by residual-pattern scan plus metadata scrub.
- If `search_for` returns no rect for a discovered identifier, try normalized variants (collapse whitespace, swap hyphen types) before concluding it is absent; log any identifier that cannot be located as a known risk.
- Keep the redaction idempotent: re-running on an already-redacted file must not change page count or introduce new text.