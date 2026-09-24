---
name: academic-pdf-redaction
description: Redact identifying information from PDF documents for blind review anonymization
---

## Steps
1. **Collect leak candidates from the paper itself (don’t assume they’re only in the header).**
   - Extract text for at least the **first ~2–3 pages** (title/authors/abstract area) and note:
     - author full names (as written)
     - affiliations / labs / institutions
     - email addresses / usernames
     - funding / acknowledgements names
     - venue strings (e.g., “ICML”, “NeurIPS”, “Accepted at …”, “Camera-ready”, workshop names)
     - arXiv/DOI/URL strings
   - These *paper-specific strings* become your **exact-match redaction patterns**.
2. **Redaction scope: apply across the *entire document*, including References.**
   - Do **not** skip the References section: author names, venues, and arXiv links in references can still reveal authorship (e.g., self-citations).
   - Still avoid overbroad redaction: prefer **full phrases / full names / complete identifiers**, not lone surnames.
3. **Use PyMuPDF (fitz) to redact only matched regions (no page-wide wipes).**
   ```python
   import fitz, os, re
   def redact_with_pymupdf(input_path: str, output_path: str, patterns: list[str]):
       doc = fitz.open(input_path)
       # Clear metadata (avoid author/tool leakage)
       doc.set_metadata({})
       for page in doc:
           for pat in patterns:
               for rect in page.search_for(pat):
                   page.add_redact_annot(rect, fill=(0, 0, 0))
           page.apply_redactions()
       os.makedirs(os.path.dirname(output_path), exist_ok=True)
       doc.save(output_path, garbage=4, deflate=True)
       doc.close()
       verify_redaction(input_path, output_path, patterns)
   ```
4. **Include robust patterns for common leaks (and keep them consistent through verification).**
   - Always include (as exact strings and/or regex-derived strings you also search for explicitly):
     - emails (e.g., “@”, or specific emails found)
     - arXiv IDs *and* arXiv URLs (e.g., `arXiv:2401.01234`, `arxiv.org/abs/2401.01234`, `https://arxiv.org/abs/...`)
     - DOI prefix strings actually present (e.g., `doi:`, `10.` segments if they appear verbatim)
     - venue tokens that triggered earlier scans (e.g., if you ever saw “ICML”, keep **“ICML”** in the final verification needles; don’t replace it only with longer variants)
5. **Verification must re-check *all previously hit needles* (don’t “narrow” the list later).**
   ```python
   import fitz
   def verify_redaction(original_path, output_path, needles):
       orig = fitz.open(original_path)
       redc = fitz.open(output_path)
       orig_len = sum(len(p.get_text()) for p in orig)
       redc_len = sum(len(p.get_text()) for p in redc)
       if len(redc) != len(orig):
           raise ValueError("Page count changed")
       if redc_len < 1000 or redc_len < orig_len * 0.7:
           raise ValueError("Too much text removed / corrupted output")
       # Stable needle scan: check that none of the chosen leak strings remain anywhere.
       full_text = "\n".join(p.get_text() for p in redc)
       hits = [n for n in needles if n and (n in full_text)]
       if hits:
           raise ValueError(f"Leak needles still present: {hits}")
       orig.close(); redc.close()
   ```
## Expected Result
A redacted PDF where **no authorship-revealing strings remain anywhere in the document (including References)**, PDF metadata is cleared, page count is unchanged, and most content remains intact (roughly ≥70% text retained).
