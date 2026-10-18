# Robust span-level redaction

Use this reference when `page.search_for(literal)` is insufficient: the target may wrap, rotate, or use Unicode variants, or a leak survived the first pass. The algorithm walks `page.get_text("dict")` spans, so every rendered glyph run is inspected directly, regardless of line wrap, rotation, or codepoint variant.

## When to read this

- Any target longer than a single ASCII word (grant signatures, author full names, affiliations, venue strings).
- Any PDF with a rotated banner (arXiv preprint page 1, journal watermarks).
- Any residual leak flagged by `verify_no_leaks` after the first redaction pass.

Skip when every target is a short ASCII token, no rotated runs exist, and the first pass already produces a clean leak re-scan.

## Full algorithm

```python
import fitz, re, unicodedata

def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)

def expand_tokens(phrases: list[str]) -> set[str]:
    """Given full-phrase targets, emit tokens + Unicode variants.

    Splits each phrase on whitespace AND non-alphanumeric so wrapped,
    hyphenated, or quoted sub-strings still match. Also emits curly/straight
    quote and hyphen/en-dash variants of the full phrase.
    """
    tokens: set[str] = set()
    for phrase in phrases:
        p = nfkc(phrase)
        tokens.add(p)
        # Variants: straight <-> curly quotes; hyphen <-> en-dash
        tokens.add(p.replace("'", "\u2019").replace('"', "\u201d"))
        tokens.add(p.replace("\u2019", "'").replace("\u201d", '"'))
        tokens.add(p.replace("-", "\u2013"))
        tokens.add(p.replace("\u2013", "-"))
        # Sub-tokens from splitting on non-alphanumeric runs
        for sub in re.split(r"[^\w]+", p):
            if len(sub) >= 2:  # drop single-char fragments
                tokens.add(sub)
    return {t for t in tokens if t.strip()}

def redact_pdf(input_path: str, output_path: str,
               regexes: list[str], phrases: list[str]) -> list[tuple]:
    """Redact every span matching any regex or expanded token.

    Returns the list of (page, span_text, matcher) hits for logging.
    """
    doc = fitz.open(input_path)
    ref_idx = _find_references(doc)
    compiled = [re.compile(p) for p in regexes]
    tokens = expand_tokens(phrases)
    hits = []
    for pno, page in enumerate(doc):
        if ref_idx is not None and pno >= ref_idx:
            continue
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = nfkc(span["text"])
                    matched = None
                    for c in compiled:
                        if c.search(text):
                            matched = c.pattern; break
                    if matched is None:
                        for tok in tokens:
                            if tok and tok in text:
                                matched = f"token:{tok}"; break
                    if matched:
                        rect = fitz.Rect(span["bbox"])
                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        hits.append((pno, span["text"], matched))
        page.apply_redactions()
    doc.save(output_path)
    doc.close()
    return hits

def _find_references(doc) -> int | None:
    for i, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                t = "".join(s["text"] for s in line.get("spans", [])).strip().lower()
                if t in {"references", "bibliography"} or t.startswith("references"):
                    return i
    return None
```

## Runtime branches

The algorithm must handle three structural cases differently. Each branch is already covered by the span walk above, but confirm each applies on the current PDF before trusting a clean result.

### Branch A — standard horizontal text, no wrap concern

Span `dir == (1.0, 0.0)` and target fits on one line. Span walk is equivalent to `search_for`; either works. No action needed.

### Branch B — target wraps across a soft line break

Example: `"ARO W911NF-23-2-\n0224"`. The multi-word literal returns zero rectangles from `search_for`. The span walk still redacts each piece because `expand_tokens` emits `ARO`, `W911NF`, `W911NF-23-2-`, `0224`, and the sub-token `23-2-0224`. Verify after redaction that no fragment survives:

```python
# After redact_pdf:
doc = fitz.open(output_path)
leftover = []
for pno, page in enumerate(doc):
    txt = nfkc(page.get_text())
    for tok in expand_tokens(phrases):
        if tok in txt:
            leftover.append((pno, tok))
doc.close()
# Corrective action on failure:
# A sub-token survived -> re-run redact_pdf; the span containing it
# did not match because span["text"] was itself split further. Shorten
# the minimum sub-token length in expand_tokens (e.g. from 2 to 1) or
# add the surviving fragment as an explicit phrase and re-run.
```

### Branch C — rotated / vertical text (arXiv banner, journal watermark)

Spans have `span["dir"] != (1.0, 0.0)`; `fitz.Rect(span["bbox"])` still gives the correct redaction rectangle because PyMuPDF stores the bbox in page coordinates. The span walk works without special handling, but `search_for` silently fails. To confirm the branch triggered:

```python
doc = fitz.open(input_path)
for pno, page in enumerate(doc):
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("dir", (1.0, 0.0)) != (1.0, 0.0):
                    print(f"page {pno}: rotated span '{span['text']}' at {span['bbox']}")
doc.close()
# Corrective action on failure:
# If a rotated span was listed above but its text still appears in
# page.get_text() of the output, the redact_annot was placed but not
# applied. Re-run with page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
# or draw an opaque filled rect over fitz.Rect(span["bbox"]) as a fallback.
```

## Diagnosis flow for a residual leak

When `verify_no_leaks` raises after a redaction pass, do NOT just append the leaked literal to `phrases` and re-run. Walk this flow:

1. **Which pattern surfaced the hit?** If `token:*`, go to step 2. If a regex, go to step 4.
2. **Was the hit a sub-token of a wrapped phrase?** Dump the page's `get_text("dict")` and locate the span containing the hit. If the span text matches the hit but no phrase was tokenized to it, extend `expand_tokens` (lower min length, add explicit sub-token).
3. **Was the hit on a rotated span?** Check `span["dir"]`. If rotated, confirm the span walk ran on that page and `apply_redactions` succeeded; fall back to an opaque filled rect over the span bbox.
4. **Did a regex miss because of a Unicode variant?** Compare `span["text"]` codepoints to the regex. Normalize both sides with NFKC before matching (already done above); if the glyph is a ligature (fi, fl) that NFKC does not split, add the ligature form to the regex explicitly.
5. **Was the leak class missing from `regexes`?** Add a new regex (new grant agency, new ID format) and re-run.

After any corrective action, re-run `redact_pdf` on the **original** input (not the already-redacted output) and re-run `verify_no_leaks`. Terminate only when the verification function returns an empty hit list.

## Verification wrapper

```python
def redact_until_clean(input_path, output_path, regexes, phrases,
                      max_iters: int = 4):
    """Redact and re-scan until clean or max_iters hit."""
    for attempt in range(max_iters):
        hits = redact_pdf(input_path, output_path, regexes, phrases)
        # Re-scan the output
        doc = fitz.open(output_path)
        ref_idx = _find_references(doc)
        compiled = [re.compile(p) for p in regexes]
        tokens = expand_tokens(phrases)
        residual = []
        for pno, page in enumerate(doc):
            if ref_idx is not None and pno >= ref_idx:
                continue
            text = nfkc(page.get_text())
            for c in compiled:
                for m in c.finditer(text):
                    residual.append((pno, m.group(0), c.pattern))
            for tok in tokens:
                if tok in text:
                    residual.append((pno, tok, "token"))
        doc.close()
        if not residual:
            return hits  # clean
        # Corrective action: widen mechanism before retry
        print(f"iter {attempt}: {len(residual)} residual leaks, widening")
        for pno, txt, matcher in residual[:10]:
            if matcher == "token":
                phrases.append(txt)  # also widens sub-tokens via expand_tokens
            # regex hits mean the regex matched but the span walk missed
            # the span -> inspect span["dir"] / bbox manually
    raise RuntimeError(f"did not converge in {max_iters} iters: {residual[:5]}")
```

Verification step: call `redact_until_clean`; on `RuntimeError`, open the output in a PDF viewer and locate the residual string visually — the span almost certainly has `dir != (1,0)` or is embedded as an image (OCR text layer only). Fall back to drawing opaque filled rectangles over the span bbox, or OCR-redact if the content is in a raster image.
