---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review

Redact identifying information from academic papers for blind review.

## CRITICAL RULES

1. **Do NOT blanket-skip References/Appendix** - Keep citations intact, but still scan the *entire PDF* (including References/Appendix) for author-identifying items (names, affiliations, emails, personal URLs, arXiv IDs, acceptance/camera-ready statements, etc.) and redact **only exact matches**.
2. **ONLY redact specific text matches** - Never redact entire pages/regions
3. **VERIFY output** - Check that 80%+ of original text remains

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

## Patterns / Literals to Redact (Whole Document)

**IMPORTANT:** PyMuPDF’s `page.search_for()` performs **literal substring search** (not wildcard / glob / regex). So patterns like `*@*.edu` or `arXiv:XXXX.XXXXX` will **not** match anything unless you first convert them into the **exact strings that appear in the PDF**.

**Rule of thumb:**
- For **names / affiliations / venues / acceptance statements**, supply **full phrases** you saw in the PDF.
  - ✅ "John Smith" (full name)
  - ❌ "Smith" (partial — risks hitting citations like “Smith et al.”)
- For **structured identifiers** (emails, URLs, arXiv IDs, ORCIDs, some DOIs), first **extract exact occurrences** from the PDF text (using regex over extracted text), then pass those extracted strings as literals to redact.

Common author-identifying items to search/redact (as exact literals once found):
1. Author names (full names only)
2. Affiliations / institutions / lab or company names
3. Emails (e.g., "name@domain.edu")
4. Personal / lab / code URLs (author pages, GitHub user/org links, project sites)
5. arXiv IDs / arxiv.org URLs
6. ORCID IDs
7. Acceptance/camera-ready statements and venue/track identifiers if deanonymizing
8. Acknowledgements that name specific people or grants that identify the authors

**Note on DOIs:** DOIs are not always author-identifying, but can deanonymize by uniquely locating a public version. Treat them as optional/conditional depending on the anonymization policy you are following.

## PyMuPDF (fitz) - Recommended Approach

```python
import fitz
import os
import re

# Regexes are used ONLY to *extract exact literals* from text.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"\bhttps?://\S+\b|\bwww\.\S+\b", re.IGNORECASE)
ARXIV_RE = re.compile(
    r"\barXiv:\s*\d{4}\.\d{4,5}(?:v\d+)?\b|\barxiv\.org/abs/\d{4}\.\d{4,5}(?:v\d+)?\b",
    re.IGNORECASE,
)
ORCID_RE = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")
DOI_RE = re.compile(r"\b10\.\d{4,9}/\S+\b", re.IGNORECASE)


def _cleanup_literal(s: str) -> str:
    # Strip common trailing punctuation captured from running text.
    return s.strip().rstrip(")].,;:")


def collect_leak_literals(doc: fitz.Document, *, include_doi: bool = False) -> list[str]:
    """Extract exact strings (emails/urls/arXiv/etc.) that should be redacted as literals."""
    found: set[str] = set()
    regexes = [EMAIL_RE, URL_RE, ARXIV_RE, ORCID_RE]
    if include_doi:
        regexes.append(DOI_RE)

    for page in doc:
        txt = page.get_text("text") or ""
        for rx in regexes:
            for m in rx.finditer(txt):
                lit = _cleanup_literal(m.group(0))
                if lit:
                    found.add(lit)

    # Redact longer strings first to reduce partial-overlap issues.
    return sorted(found, key=len, reverse=True)


def sanitize_metadata(doc: fitz.Document) -> None:
    """Clear document info dict + XMP metadata (if present)."""
    meta = doc.metadata or {}
    for k in list(meta.keys()):
        meta[k] = ""
    doc.set_metadata(meta)

    # Remove XMP metadata if supported by this PyMuPDF build.
    try:
        doc.set_xml_metadata("")
    except Exception:
        pass


def remove_links_and_annots(page: fitz.Page) -> None:
    """Remove link annotations / other annotations that can embed deanonymizing URLs."""
    # Links
    for link in page.get_links() or []:
        try:
            page.delete_link(link)
        except Exception:
            pass

    # Other annotations (comments, file attachments, etc.)
    annots = page.annots()
    if annots:
        for a in list(annots):
            try:
                page.delete_annot(a)
            except Exception:
                pass


def redact_with_pymupdf(
    input_path: str,
    output_path: str,
    manual_literals: list[str],
    *,
    auto_extract_structured: bool = True,
    include_doi: bool = False,
):
    """Redact author-identifying info from PDF using true redactions.

    - `manual_literals`: full names/affiliations/venues/phrases you want removed (exact strings).
    - `auto_extract_structured`: if True, regex-extract emails/URLs/arXiv/ORCID as exact literals and redact them.
    - `include_doi`: optional; set True only if DOI redaction is required by your policy.
    """
    doc = fitz.open(input_path)

    extracted_literals = collect_leak_literals(doc, include_doi=include_doi) if auto_extract_structured else []
    # Combine, dedupe, and keep longer-first ordering.
    all_literals = sorted({s for s in (manual_literals + extracted_literals) if s}, key=len, reverse=True)

    for page in doc:
        for lit in all_literals:
            for rect in page.search_for(lit):
                page.add_redact_annot(rect, fill=(0, 0, 0))

        # Apply redactions (removes underlying content; not just an overlay).
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)
        remove_links_and_annots(page)

    sanitize_metadata(doc)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()

    # MUST verify after saving
    verify_redaction(input_path, output_path, forbidden_literals=all_literals)
```

## REQUIRED: Verification Function

**Always run this after ANY redaction to catch errors early:**

```python
import fitz

def verify_redaction(original_path, output_path, forbidden_literals=None):
    """Verify redaction didn't corrupt the PDF and that obvious leaks are gone.

    NOTE: This cannot reliably detect image-only identity leaks; still do visual inspection.
    """
    orig = fitz.open(original_path)
    redc = fitz.open(output_path)

    orig_len = sum(len(p.get_text("text") or "") for p in orig)
    redc_len = sum(len(p.get_text("text") or "") for p in redc)

    print(f"Original: {len(orig)} pages, {orig_len} chars")
    print(f"Redacted: {len(redc)} pages, {redc_len} chars")
    if orig_len:
        print(f"Retained: {redc_len/orig_len:.1%}")

    # DEFENSIVE CHECKS - fail fast if something went wrong
    if len(redc) != len(orig):
        raise ValueError(f"Page count changed: {len(orig)} -> {len(redc)}")
    if redc_len < 1000:
        raise ValueError(f"PDF corrupted: only {redc_len} chars remain!")
    if orig_len and redc_len < orig_len * 0.8:
        raise ValueError(f"Too much removed: kept only {redc_len/orig_len:.0%}")

    # Metadata leakage check
    meta = redc.metadata or {}
    leaked = {k: v for k, v in meta.items() if isinstance(v, str) and v.strip()}
    if leaked:
        raise ValueError(f"Metadata still contains values (clear them!): {leaked}")

    # Optional: confirm forbidden literals are no longer text-extractable
    if forbidden_literals:
        blob = "\n".join((p.get_text("text") or "") for p in redc).lower()
        hits = [s for s in forbidden_literals if s and s.lower() in blob]
        if hits:
            raise ValueError(f"Forbidden literals still present in extracted text: {hits[:10]}")

    orig.close()
    redc.close()
    print("✓ Verification passed")
```
