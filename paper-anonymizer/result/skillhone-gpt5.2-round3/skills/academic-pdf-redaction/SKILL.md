---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review (Academic Papers)

Redact identifying information from academic papers for blind review **without destroying the paper content**.

## CRITICAL RULES

1. **Preserve the References section**
   - Do **not** remove entire citations or redact common author last names inside citations.
   - It is usually acceptable to redact **deanonymizing identifiers** that can appear anywhere (e.g., arXiv IDs/URLs, emails, camera-ready venue footers), even if they occur on References pages.
2. **Only redact specific text matches**
   - Use `page.search_for(<exact string>)` + `add_redact_annot` + `apply_redactions()`.
   - Never “black out” regions by drawing rectangles, and never loop over all text blocks.
3. **Clear PDF metadata**
   - PDF properties (Title/Author/Creator/Producer + XMP) can leak identity.
4. **Verify output**
   - Page count must not change.
   - As a safety check, ensure ~**80%+** of extractable text remains (tune if you knowingly redact more).
   - Run a leak scan (emails, arXiv IDs/URLs, ORCID, etc.) and iterate until clean.

## Use the included helper script (recommended)

This skill ships with a reusable helper:
- `skills/academic-pdf-redaction/scripts/redact_academic_pdf.py`

It implements:
- literal-only redaction (`search_for` + redaction annotations + `apply_redactions`)
- separate **pre-References** vs **global** pattern sets
- regex-driven redaction via **token extraction** (regex over extracted text → redact exact matched tokens)
- metadata clearing (Info + XMP, best-effort)
- external link annotation stripping (removes hidden URL targets like arXiv/ORCID/mailto)
- post-save verification (page count unchanged; retained-text ratio threshold)
- generic leak scan (emails, arXiv IDs/URLs, ORCID-like IDs)

Typical usage:

```bash
python3 skills/academic-pdf-redaction/scripts/redact_academic_pdf.py \
  --input <input.pdf> --output <output.pdf> \
  --config patterns.json
```

`patterns.json` (all keys optional):

```json
{
  "pre_ref_literals": ["Full Author Name", "Full Institution Name", "Correspondence:"],
  "global_literals": ["Proceedings of …", "Accepted at …"],
  "pre_ref_regexes": [],
  "global_regexes": [],
  "min_retained_ratio": 0.80,
  "redact_dois": false
}
```

Pattern hygiene:
- Prefer **full phrases / full lines**. Avoid generic keywords like `accepted` or `conference` as standalone patterns (they appear widely in citations and can destroy content).
- Keep **global** patterns tightly scoped to high-confidence identifiers (emails, arXiv IDs/URLs, ORCID, venue footers).

## Common Pitfalls to Avoid

```python
# ❌ WRONG - This removes ALL text from the page:
for block in page.get_text("blocks"):
    page.add_redact_annot(fitz.Rect(block[:4]))

# ❌ WRONG - Drawing rectangles over text (text remains extractable):
page.draw_rect(fitz.Rect(0, 0, 600, 100), fill=(0,0,0))

# ✅ CORRECT - Only redact specific search matches:
for rect in page.search_for("John Smith"):
    page.add_redact_annot(rect, fill=(0, 0, 0))
page.apply_redactions()
```

## What to Redact (Typical Author‑Leaking Signals)

### Redact **before References** (main body + front matter)

Use **FULL phrases** wherever possible to avoid accidental matches in citations:
- Author names (full names)
- Affiliations / institutions / locations
- Correspondence lines, email addresses
- “Equal contribution” footnotes if they identify authors
- Acknowledgements that name people/labs
- Personal or project URLs that identify authors (GitHub usernames, lab pages, personal homepages)
- Accepted‑venue statements (e.g., “Accepted at …”, “Proceedings of …”, workshop names)

### Redact **globally** (including References) when they deanonymize

These often uniquely identify the paper and can appear in citations:
- arXiv identifiers and URLs (`arXiv:YYYY.NNNNN`, `arxiv.org/abs/...`, `arxiv.org/pdf/...`)
- Email addresses (regex)
- ORCID IDs (`0000-0000-0000-000X`, or `orcid.org/...` links)
- Camera‑ready / proceedings footers or copyright lines that reveal venue/year
- **Hidden link targets** (PDF link annotations) that point to identifying URLs even if the visible text is already redacted

## Robust “References starts at page …” Detection

**Do not** do `if "references" in page.get_text().lower()` — the word “references” often appears in the body.

Instead, detect a **section heading** near the top of a page:
- Line equals `References` / `REFERENCES`
- Line matches like `6. References` / `6 References`
- Also consider `Bibliography`

Heuristic example:
```python
import re

def find_references_start_page(doc):
    heading_re = re.compile(r"^(?:\d+\s*[\.)]?)?\s*(references|bibliography)\s*$", re.I)

    for pno, page in enumerate(doc):
        # Look only at early lines where headings usually appear.
        lines = [ln.strip() for ln in page.get_text("text").splitlines()[:250] if ln.strip()]
        for ln in lines[:60]:
            if heading_re.match(ln):
                return pno
    return None
```

## PyMuPDF (fitz) – Recommended Approach

Key ideas:
- Maintain two redaction sets:
  - **Pre‑References** patterns (names/affiliations/etc.)
  - **Global** patterns (arXiv IDs/URLs, emails, ORCID, venue footers)
- Apply **footer/venue** patterns on **every page** (they often appear even on References pages).
- Clear **Info metadata** *and* **XMP metadata** when possible.

```python
import os
import re
import fitz  # PyMuPDF

META_KEYS = [
    "title", "author", "subject", "keywords",
    "creator", "producer",
    "creationDate", "modDate", "trapped",
]

def clear_metadata(doc: fitz.Document) -> None:
    # Info dictionary
    try:
        doc.set_metadata({k: "" for k in META_KEYS})
    except Exception:
        doc.set_metadata({})

    # XMP metadata (if present)
    for attr in ("set_xml_metadata", "setXmlMetadata"):
        if hasattr(doc, attr):
            try:
                getattr(doc, attr)("")
            except Exception:
                pass

def _search_flags():
    # Make optional flags robust across PyMuPDF versions.
    flags = 0
    for name in ("TEXT_IGNORECASE", "TEXT_DEHYPHENATE"):
        flags |= int(getattr(fitz, name, 0) or 0)
    return flags

def add_redactions_for_literal(page: fitz.Page, text: str) -> int:
    if not text or len(text.strip()) < 3:
        return 0
    rects = page.search_for(text, flags=_search_flags())
    for r in rects:
        page.add_redact_annot(r, fill=(0, 0, 0))
    return len(rects)

def add_redactions_for_regex_tokens(page: fitz.Page, page_text: str, regexes: list[str]) -> int:
    total = 0
    for rx in regexes:
        for m in re.finditer(rx, page_text, flags=re.I):
            tok = (m.group(0) or "").strip()
            tok = tok.rstrip(").,;:]}")
            if len(tok) < 3:
                continue

            # Try a few common URL variants (helps when the PDF drops schemes).
            variants = [tok]
            if "arxiv.org/abs" in tok.lower():
                variants += ["https://" + tok.lstrip("/"), "//" + tok.lstrip("/")]

            for v in dict.fromkeys(variants):
                total += add_redactions_for_literal(page, v)

    return total

def redact_academic_pdf(
    input_path: str,
    output_path: str,
    pre_ref_literals: list[str],
    global_literals: list[str],
    pre_ref_regexes: list[str],
    global_regexes: list[str],
):
    doc = fitz.open(input_path)
    clear_metadata(doc)

    ref_start = find_references_start_page(doc)

    for pno, page in enumerate(doc):
        text = page.get_text("text")

        # 1) Always‑on redactions (footers, arXiv, emails, etc.)
        for s in global_literals:
            add_redactions_for_literal(page, s)
        add_redactions_for_regex_tokens(page, text, global_regexes)

        # 2) Pre‑References‑only redactions (names, affiliations, etc.)
        if ref_start is None or pno < ref_start:
            for s in pre_ref_literals:
                add_redactions_for_literal(page, s)
            add_redactions_for_regex_tokens(page, text, pre_ref_regexes)

        page.apply_redactions()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()

    verify_redaction(input_path, output_path)
    scan_for_common_leaks(output_path)
```

## REQUIRED: Verification + Leak Scan

Always run these checks after saving to catch silent failures.

```python
import re
import fitz

def verify_redaction(original_path: str, output_path: str, min_retained_ratio: float = 0.80) -> None:
    orig = fitz.open(original_path)
    redc = fitz.open(output_path)

    orig_len = sum(len(p.get_text()) for p in orig)
    redc_len = sum(len(p.get_text()) for p in redc)

    if len(redc) != len(orig):
        raise ValueError(f"Page count changed: {len(orig)} -> {len(redc)}")
    if redc_len < 1000:
        raise ValueError(f"PDF likely corrupted: only {redc_len} chars remain")
    if orig_len and (redc_len / orig_len) < min_retained_ratio:
        raise ValueError(f"Too much removed: retained {redc_len/orig_len:.1%}")

    orig.close()
    redc.close()

def scan_for_common_leaks(pdf_path: str) -> None:
    doc = fitz.open(pdf_path)
    text = "\n".join(p.get_text("text") for p in doc)

    # NOTE: Extracted text does not include link annotation targets. For safety,
    # also inspect PDF links (URIs) and ensure none point to deanonymizing URLs.
    link_targets = []
    try:
        for page in doc:
            for lnk in page.get_links() or []:
                if lnk.get("uri"):
                    link_targets.append(str(lnk["uri"]))
                if lnk.get("file"):
                    link_targets.append(str(lnk["file"]))
    except Exception:
        # Best-effort: not all PDFs / PyMuPDF versions expose link details.
        pass

    # Generic, reusable “suspicious” patterns (not instance‑specific).
    needles = [
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",

        # arXiv IDs (new + legacy)
        r"\barxiv\s*:\s*(?:\d{4}\.\d{4,5}(?:v\d+)?|[A-Za-z\-]+(?:\.[A-Za-z]{2})?/\d{7}(?:v\d+)?)\b",

        # arXiv URLs
        r"(?:https?:)?//(?:www\.)?arxiv\.org/(?:abs|pdf)/",
        r"\b(?:www\.)?arxiv\.org/(?:abs|pdf)/",
        r"\barxiv\.org/(?:abs|pdf)/",

        r"\b\d{4}-\d{4}-\d{4}-\d{3}[0-9X]\b",  # ORCID‑like
    ]

    hits = [rx for rx in needles if re.search(rx, text, flags=re.I)]

    # Metadata checks (Info + XMP)
    meta = doc.metadata or {}
    nonempty_info = {k: v for k, v in meta.items() if v and k not in ("format",)}
    xmp = ""
    for attr in ("get_xml_metadata", "getXmlMetadata"):
        if hasattr(doc, attr):
            try:
                xmp = getattr(doc, attr)() or ""
            except Exception:
                pass

    doc.close()

    if nonempty_info:
        raise ValueError(f"Non‑empty PDF Info metadata remains: {nonempty_info}")
    if xmp and xmp.strip():
        raise ValueError("XMP metadata remains non‑empty; clear it to avoid identity leaks")

    if link_targets:
        suspicious = [
            t
            for t in link_targets
            if any(
                needle in t.lower()
                for needle in ("arxiv.org/", "orcid.org/", "mailto:")
            )
        ]
        if suspicious:
            raise ValueError(f"Potential deanonymizing link targets remain: {suspicious[:10]}")

    if hits:
        raise ValueError(f"Potential leak patterns still present: {hits}")
```

## Practical Redaction Workflow (Recommended)

1. **Inspect inputs**
   - Extract first‑page text + metadata; list obvious author/affiliation/email strings to redact.
2. **Build pattern lists**
   - Pre‑References literals: full names, full affiliations, correspondence lines.
   - Global regexes: emails, arXiv IDs/URLs, ORCID.
   - Global literals: venue footers / accepted‑venue statements (apply to all pages).
3. **Apply redactions + save cleanly**
   - Use `garbage=4, clean=True` and clear metadata.
4. **Verify + leak scan**
   - If anything is found, iterate: add the missing literal(s) or expand the global regex token extraction.

## Notes

- `page.search_for()` is **not** regex. For regex‑based redaction, extract the exact tokens from `page.get_text("text")` first, then search/redact those tokens.
- Be cautious with partial words: redacting last names or common institutions inside References can damage citations. Prefer full phrases, and keep “global” patterns focused on high‑confidence identifiers (emails, arXiv IDs/URLs, ORCID, venue footers).
