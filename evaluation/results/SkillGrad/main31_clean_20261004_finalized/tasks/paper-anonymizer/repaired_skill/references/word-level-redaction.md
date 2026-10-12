# Word-level / bbox-derived redaction when `search_for()` fails (PyMuPDF)

Use this when your detector sees a leak in extracted text, but `page.search_for(surface_form)` returns no rectangles. This usually indicates a surface-form mismatch caused by line breaks, hyphenation, ligatures, superscripts, or glyph-level extraction differences.

## Runnable procedure: locate by words → union bbox → redact

```python
import re
import fitz


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9@./:-]+", "", s)
    return s.strip()


def union_rect(rects: list[fitz.Rect]) -> fitz.Rect:
    r = rects[0]
    for rr in rects[1:]:
        r |= rr
    return r


def redact_by_word_window(page: fitz.Page, needle: str, max_window: int = 12) -> int:
    words = page.get_text("words")  # (x0, y0, x1, y1, word, block, line, word_no)
    target = _norm(needle)

    toks = [w[4] for w in words]
    norms = [_norm(t) for t in toks]

    redacted = 0
    for i in range(len(words)):
        acc = ""
        rects: list[fitz.Rect] = []
        for j in range(i, min(len(words), i + max_window)):
            acc += norms[j]
            rects.append(fitz.Rect(words[j][0], words[j][1], words[j][2], words[j][3]))
            if target and target in acc:
                page.add_redact_annot(union_rect(rects), fill=(0, 0, 0))
                redacted += 1
                break
    if redacted:
        page.apply_redactions()
    return redacted


doc = fitz.open("input.pdf")
page = doc[0]
count = redact_by_word_window(page, "some leak string")
print("redactions_added:", count)
if count == 0:
    print("No match; broaden window or target a shorter distinctive substring")

doc.save("output.pdf", clean=True, garbage=4)
doc.close()
```

## Runtime branches

- If `redactions_added > 0`: re-run your detector sweep on the saved output.
- If `redactions_added == 0`: shorten `needle` to a distinctive fragment (e.g., domain part of an email, acronym + nearby word), increase `max_window`, and try again; if still zero, fall back to manual bbox selection by inspecting `page.get_text("words")` around where the hit appears.

## Verification step (with corrective action)

After saving `output.pdf`, rerun the same detector that produced the original hit:
- If the hit is gone: continue with the next hit/category.
- If the hit remains: repeat with a shorter fragment or use multiple passes that redact adjacent word windows; do not proceed to finalization until the detector returns empty for that category.
