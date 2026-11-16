# Academic PDF Blind-Review Redaction (Leak-Driven)

## Purpose
Redact authorship-revealing information from academic PDFs for blind review by iterating: discover likely leaks, apply targeted redactions (text-first, region-only as a fallback), sanitize metadata, then validate by re-opening and running deterministic leak scans.

## When to Use
Use when you must anonymize one or more academic PDF documents for double-blind submission where the goal is "no identifying information remains" while keeping scholarly content (including citations) readable and intact.

## Procedure
- 1) Preflight and discovery (no edits yet)
- Confirm you have: input PDF path(s), intended output location(s), and what counts as "identifying info" (unknown items must be clarified or treated as in-scope leaks).
- Open the PDF with a library that supports true redactions (not drawing overlays). Discover:
- Page count, whether text extraction returns meaningful text on most pages, and whether the PDF is scanned/non-searchable.
- Candidate leak zones (title block, first page footer, headers, acknowledgements, appendix, supplemental links, code/data availability statements).
- Decision: if most pages have near-empty extracted text, treat as scanned/non-searchable and plan a region-based strategy plus a manual spot-check requirement (do not rely on string search alone).
- 2) Build a leak detector suite (document-agnostic)
- Define detectors that can be run repeatedly on extracted text to produce (pattern, page, snippet) hits, including at least:
- Emails (simple pattern like something@something.tld).
- URLs (http(s):// and www.).
- arXiv identifiers and arXiv URLs.
- DOI patterns.
- Organization/affiliation cues (e.g., "University", "Institute", "Lab", "Department") and grant/contract-like tokens (mixed letters/digits, common prefixes) as review candidates (do not auto-redact all of these without confirmation).
- Run detectors on the current PDF text and produce a hit report with page numbers.
- Decision: create an "approved exceptions" list only for content that is explicitly allowed to remain (typically bibliographic citation strings), and keep it minimal and auditable.
- 3) Redact using a safe priority order (text-first, region-fallback)
- Text-based redaction pass:
- For each detector hit that is in-scope, generate one or more search variants (case-insensitive, whitespace-normalized, common punctuation variants) and attempt to locate occurrences on the page.
- Apply redactions only to the matched rectangles, then apply redactions for that page.
- Conditional policy for References and citations:
- Preserve citation entries as scholarly content, but do NOT automatically exempt the entire References section.
- Redact direct identifiers anywhere they appear (emails, URLs, arXiv IDs/URLs, author homepages, repository links, contact addresses), including inside References, unless an explicit requirement says otherwise.
- Region-based fallback (use only when needed):
- Trigger: detectors show a leak on a page but text search cannot locate it, or the leak appears in repeating headers/footers/logos, or the PDF is largely non-searchable.
- Action: constrain region redaction to the smallest repeated area (header/footer band or a clearly identified block), and apply consistently across affected pages.
- Checkpoint: after any region strategy change, re-run extraction and leak scan to ensure you did not black out major content unintentionally.
- 4) Sanitize metadata and validate by reload-and-scan (hard gate)
- Remove or overwrite PDF metadata fields that can contain authorship (author, creator, producer, title keywords, custom metadata) using capabilities available in the chosen library/tool.
- Save to the target output, then re-open the saved PDF and run all validation checks:
- Openable without errors; page count unchanged.
- Leak scan re-run on the output PDF returns zero in-scope hits after applying the exception policy.
- If any hits remain: iterate back to step 3; do not claim completion.
- Execution anchor (required): print a per-page hit report and then print a single sentinel line such as LEAK_SCAN_PASS only when zero in-scope hits remain after reload.

## Constraints / Pitfalls
- Do not rely on "percent of text retained" as a success criterion; the primary success condition is absence of identifying info after reload-and-scan, plus basic PDF integrity checks.
- Do not use "draw black boxes" overlays as redaction; use true redaction annotations and apply them, and always re-open the saved PDF to confirm the content is actually removed (not just visually covered).