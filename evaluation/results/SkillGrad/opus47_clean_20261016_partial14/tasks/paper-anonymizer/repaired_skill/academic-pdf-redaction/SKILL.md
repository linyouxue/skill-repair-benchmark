---
name: academic-pdf-redaction
description: Redact identifying text from academic PDFs for blind review while preserving the References section byte-for-byte.
---

# PDF Redaction for Blind Review

Redact identifying information from academic papers for blind review. The deliverable is a redacted PDF whose pre-References pages carry zero identity-leaking strings and whose References section is unchanged.

## Core rules

1. **Preserve References section** — self-citations stay intact; skip redaction on and after the References page.
2. **Redact at the span/token level, not multi-word literals** — `page.search_for(long phrase)` silently misses wrapped, rotated, and Unicode-variant text.
3. **Verify by re-scanning the redacted output with the same leak regexes** — passing a page-count / char-retention check is not sufficient.

## Workflow

1. Enumerate leak classes on each pre-References page (authors, affiliations, emails, venues, arXiv IDs, DOIs, grant signatures, acknowledgements, equal-contribution footnotes, "Preprint"/banner text, venue footers).
2. Build a **regex list** for class-based leaks (arXiv, DOI, email, grant) and a **token list** for named entities (split each full name/affiliation/grant into individual tokens; include Unicode variants).
3. Walk `page.get_text("dict")` spans and redact any span whose text matches a regex or token (see `references/robust-redaction.md`).
4. Save, then re-open the output and run the leak re-scan under "Verification" below. On any hit, treat it as a mechanism failure, widen the strategy, and re-run until clean.

## Leak-class regex list (pre-References pages)

Use these as the primary matcher — not multi-word literal strings.

```python
LEAK_REGEXES = [
    r"arXiv:\s*\d{4}\.\d{4,5}(v\d+)?",           # arXiv IDs (also in body citations)
    r"\b10\.\d{4,9}/\S+",                         # DOIs
    r"[\w.+-]+@[\w.-]+\.\w+",                     # emails
    r"\b(ARO|NSF|DARPA|ONR|DOE|NIH|AFOSR)\b"      # grant-agency signatures;
    r"(\s*[\w./-]*\d{3,})?",                      #   trailing grant number may wrap
    r"\bPreprint\b",                               # preprint banner text
    r"\bISSN\s*[\d-]+",                           # venue footers
]
```

Named-entity targets (authors, affiliations, acknowledgement names, venue names) are task-specific — enumerate from the PDF, then **tokenize**: split a full name into its sub-tokens plus the full phrase, and add curly-quote / straight-quote and hyphen / en-dash variants of any phrase containing those characters.

## Span-level redaction (primary mechanism)

Walk the glyph stream directly so wrapped lines, rotated spans, and Unicode variants are all caught in one pass.

```python
import fitz, re, unicodedata

def redact_page(page, regexes, tokens):
    """Redact every span whose normalized text matches any regex or token."""
    compiled = [re.compile(p) for p in regexes]
    norm_tokens = {unicodedata.normalize("NFKC", t) for t in tokens}
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = unicodedata.normalize("NFKC", span["text"])
                if any(c.search(text) for c in compiled) or \
                   any(tok in text for tok in norm_tokens):
                    page.add_redact_annot(fitz.Rect(span["bbox"]), fill=(0, 0, 0))
    page.apply_redactions()
```

Read `references/robust-redaction.md` when any target may wrap across lines, appear in a rotated/vertical banner, use curly quotes or en-dashes, or when a leak remains after one pass. Skip when every target is a short single-word ASCII token and no rotated runs exist on the page.

## Why `page.search_for(literal)` is not enough

`search_for` returns rectangles only for contiguous glyph runs on a single line in default orientation with exact Unicode codepoints. It silently returns `[]` when:

- the target wraps across a soft line break or hyphenation (e.g. a grant number splits mid-string);
- the text is rotated (e.g. a vertical banner — one glyph per line in the extracted coordinate system);
- the stored codepoints differ (curly vs straight quotes, en-dash vs hyphen-minus, ligatures).

Treat `search_for` as a convenience shortcut for short single-token ASCII targets only, and always back it up by the span walk above.

## Skipping the References section

```python
def references_page_index(doc):
    for i, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                txt = "".join(s["text"] for s in line.get("spans", [])).strip().lower()
                if txt in {"references", "bibliography"} or txt.startswith("references"):
                    return i
    return None  # no References section found; redact all pages conservatively
```

Pages `>= references_page_index(doc)` are left untouched. Also skip them in the leak re-scan to avoid flagging legitimate self-citations.

## Verification: re-scan to convergence

Structural checks (page count, char retention) are necessary but not sufficient. Verification **must** re-scan the redacted output with the same leak regexes and fail on any hit outside the References section.

```python
import fitz, re, unicodedata

class LeakRemainingError(AssertionError): pass

def verify_no_leaks(output_path, regexes, tokens, ref_page_idx):
    doc = fitz.open(output_path)
    compiled = [re.compile(p) for p in regexes]
    norm_tokens = {unicodedata.normalize("NFKC", t) for t in tokens}
    hits = []
    for pno, page in enumerate(doc):
        if ref_page_idx is not None and pno >= ref_page_idx:
            continue
        text = unicodedata.normalize("NFKC", page.get_text())
        for c in compiled:
            for m in c.finditer(text):
                hits.append((pno, m.group(0), c.pattern))
        for tok in norm_tokens:
            if tok in text:
                hits.append((pno, tok, "token"))
    # structural sanity
    o_len = sum(len(p.get_text()) for p in fitz.open(output_path))
    doc.close()
    if hits:
        raise LeakRemainingError(f"{len(hits)} leaks remain: {hits[:5]}")
```

On `LeakRemainingError`: do **not** append the leaked literal to the token list as the only fix. Diagnose which failure mode let it through (line wrap → tokenize; rotated → confirm span walk ran; Unicode variant → normalize; missing class → add regex), widen the mechanism, and re-run `redact_page` + `verify_no_leaks` until it returns cleanly. See `references/robust-redaction.md` for the diagnosis flow and the `redact_until_clean` convergence loop.

## Common Pitfalls

- **Multi-word literal `search_for` as sole mechanism** — misses wrapped / rotated / Unicode-variant text. Use span walk + regex instead.
- **Partial-token matches damaging References** — redacting the bare surname also damages citations in References. Keep References excluded, but *also* tokenize so wrapped full names still match on pre-References pages.
- **Scope omissions on pre-References pages** — body-text arXiv IDs, DOI citations, "Preprint" banner, grant signatures (ARO/NSF/DARPA/…), and venue ISSN+page footers are leaks too, not only authors/affiliations/emails.
- **Verification that only checks structure** — printing a page-count / char-retention pass without a zero-hit leak re-scan is not sufficient; a positive leak hit is a mechanism-failure signal, not a data-list omission.
- **One-shot patch on a surfaced leak** — if the re-scan flags residual text, widen the mechanism (span walk, token split, Unicode normalize, new regex class) rather than appending that one string to the literal list and stopping.
