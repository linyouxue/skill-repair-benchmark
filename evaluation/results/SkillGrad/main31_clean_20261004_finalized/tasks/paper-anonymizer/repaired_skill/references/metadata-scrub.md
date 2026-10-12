# PDF metadata scrub (deterministic) + clean rewrite

Use this chapter when PDF metadata persists after a naive `set_metadata({})` call or when anonymization requires removing title/author/producer/creation dates.

## Procedure

```python
import fitz

DEFAULT_CLEAR_KEYS = [
    "title", "author", "subject", "keywords",
    "creator", "producer",
    "creationDate", "modDate",
    "trapped",
]


def scrub_metadata(doc: fitz.Document, extra_keys: list[str] | None = None) -> None:
    meta = dict(doc.metadata or {})
    keys = set(meta.keys()) | set(DEFAULT_CLEAR_KEYS) | set(extra_keys or [])
    for k in keys:
        meta[k] = ""
    doc.set_metadata(meta)


def save_clean(doc: fitz.Document, out_path: str) -> None:
    doc.save(out_path, clean=True, garbage=4)


def reload_and_check(out_path: str) -> dict:
    d = fitz.open(out_path)
    try:
        meta = d.metadata or {}
        remaining = {k: v for k, v in meta.items() if (v or "").strip()}
        return remaining
    finally:
        d.close()
```

## Runtime branches

- **Branch A (remaining metadata empty):** proceed.
- **Branch B (some keys still populated):**
  1) Re-open the original, scrub again including any observed non-standard keys.
  2) Save to a *new* output path with `clean=True, garbage=4`.
  3) If still present, round-trip through a different writer (e.g., render to new PDF) only if permitted by task constraints.

## Verification (required)

Run `reload_and_check`. If it returns any remaining keys, do not ship the PDF; repeat Branch B until empty (or explicitly documented as out of scope).
