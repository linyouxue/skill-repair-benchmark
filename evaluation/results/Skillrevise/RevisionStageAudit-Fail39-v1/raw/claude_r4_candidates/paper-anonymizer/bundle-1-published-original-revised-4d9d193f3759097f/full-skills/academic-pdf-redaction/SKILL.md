# Academic PDF Redaction for Blind Review

## Purpose
Anonymize an academic PDF so no author-identifying literal or identifier pattern remains in page text, headers, footers, or document metadata, while preserving document structure and most body text.

## When to Use
A task requires producing a blind-review version of a PDF where authorship, affiliations, contact details, grants, venue, and identifier URLs must not be recoverable from the output.

## Procedure
- Discover identity tokens dynamically. Open the PDF with PyMuPDF. From page 1 extract candidate author names, affiliations, emails, correspondence lines, and equal-contribution footnotes. Scan all pages to collect strings that repeat in top/bottom header-footer bands (likely running author/title). Build an `identity_literals` set. Do not hardcode names.
- Build regex patterns for document-wide identifiers: email (`[\w.+-]+@[\w.-]+\.\w+`), arXiv IDs (`arXiv:\d{4}\.\d{4,5}(v\d+)?`), arxiv URLs (`https?://arxiv\.org/\S+`), DOIs (`10\.\d{4,9}/\S+`), grant/contract numbers (e.g. `[A-Z]\d{2,}[A-Z0-9-]+`), and a configurable list of venue/affiliation regexes derived from discovery.
- Apply a two-tier redaction policy per page:
- Locate a `References`/`Bibliography` header via case-insensitive text search; if absent, treat the whole document as pre-references.
- Pre-references pages: redact `identity_literals` AND all regex matches.
- References and after: redact only regex-based identifier matches (self-citation text may remain). For every regex hit, call `page.search_for(match)`; if it returns no rects, retry with whitespace-normalized and sub-token variants before giving up.
- Use `page.add_redact_annot(rect, fill=(0,0,0))` then `page.apply_redactions()`. Never redact whole blocks or draw filled rectangles over regions.
- Clear metadata: `doc.set_metadata({})` and strip XMP (`doc.set_xml_metadata("")`). Save to output path.
- Leak-scan verification loop (REQUIRED): reopen the output; for each page assert zero regex hits and zero `identity_literals` hits. If any leak is found, log it, re-run step 3 on offending pages, and repeat up to 3 iterations. Also assert page count unchanged and total text retention above a reasonable floor (e.g. 50%). Fail loudly if the leak-scan still finds hits after the final iteration.

## Constraints / Pitfalls
- Verification must assert absence of sensitive patterns, not just text retention; retention-only checks produce false certainty.
- Never iterate `page.get_text("blocks")` to add redact annots over block rects; redact only rects returned by `page.search_for` on specific matches.
- Do not hardcode author names, venues, or affiliations into the skill; derive them per document in step 1.
- If `References` header detection is ambiguous, prefer over-redaction (treat whole doc as pre-references) over leaking identity.
- Keep the redact->scan loop bounded (e.g. 3 iterations) to avoid infinite loops on unresolvable matches; surface remaining leaks as an error.