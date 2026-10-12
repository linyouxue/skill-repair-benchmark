# Leak inventory → redact → re-scan loop (PDF anonymization)

Use this chapter when you cannot trust a pre-enumerated list of identifying strings and must systematically discover leaks across the whole PDF.

## Procedure

### 1) Inventory candidates across all pages

```python
import re
import fitz

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"\b(?:https?:)?//[^\s)\]}>,]+")
ARXIV_ID_RE = re.compile(r"\barXiv\s*:?\s*\d{4}\.\d{4,5}(?:v\d+)?\b", re.I)
ARXIV_URL_RE = re.compile(r"\b(?:https?:)?//arxiv\.org/abs/\d{4}\.\d{4,5}(?:v\d+)?\b", re.I)


def scan_doc(path: str) -> dict[str, set[str]]:
    doc = fitz.open(path)
    try:
        hits = {"email": set(), "url": set(), "arxiv_id": set(), "arxiv_url": set()}
        for page in doc:
            text = page.get_text() or ""
            hits["email"].update(EMAIL_RE.findall(text))
            hits["url"].update(URL_RE.findall(text))
            hits["arxiv_id"].update(ARXIV_ID_RE.findall(text))
            hits["arxiv_url"].update(ARXIV_URL_RE.findall(text))
        return hits
    finally:
        doc.close()
```

### 2) Expand surface forms (variant enumeration)

Branch on whether any detector hit cannot be located via `page.search_for`.

```python
import re

def expand_variants(token: str) -> set[str]:
    v = {token}
    v.add(token.strip(".,;:)"]))
    v.add(token.replace("https://", "//").replace("http://", "//"))
    v.add(re.sub(r"\s+", " ", token))
    return {t for t in v if t}
```

- **Branch A (search_for finds rectangles):** redact the exact token.
- **Branch B (search_for finds none):** try variants (whitespace/punctuation/protocol). If still none, fall back to locating by extracting words and matching a normalized join; then re-run `search_for` on that reconstructed surface form.

### 3) Redact and iterate

```python
import fitz

def redact_tokens(input_path: str, output_path: str, tokens: set[str]):
    doc = fitz.open(input_path)
    try:
        for page in doc:
            for tok in sorted(tokens, key=len, reverse=True):
                for rect in page.search_for(tok):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()
        doc.save(output_path, clean=True, garbage=4)
    finally:
        doc.close()
```

## Verification (required)

1) Re-scan the saved output with `scan_doc`.
2) If any hits remain:
- If remaining hits are **allowed** (e.g., general-domain URLs that are not author-identifying), document why and stop.
- Otherwise, add the remaining surface forms to the token set (plus variants) and run another redact pass.

If repeated iterations do not reduce hits, switch strategy: inspect the page where the hit occurs (use `page.get_text("words")`) to understand line-break or glyph issues, then add a more faithful surface form and retry.
