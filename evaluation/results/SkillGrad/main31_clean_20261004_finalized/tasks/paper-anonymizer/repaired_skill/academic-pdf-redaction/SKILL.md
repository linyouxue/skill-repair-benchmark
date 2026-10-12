---
name: academic-pdf-redaction
description: Redact authorship-identifying content from academic PDFs for blind review using an inventory→redact→re-scan loop with scope rules and strict deliverable verification.
---

# PDF Redaction for Blind Review

Redact identifying information from academic papers for blind review.

## CRITICAL RULES

1. **PRESERVE References content** — do not remove self-citations wholesale, but still redact globally-disallowed identifiers (see scope policy below).
2. **ONLY redact specific text matches** — never redact whole pages/regions unless explicitly instructed.
3. **TOOL CALLS MUST BE REAL** — pasted JSON / “would run X” text is not an executed step; if you notice this happened, immediately re-run via a real tool invocation.
4. **VERIFY output** — do not declare done until required deliverables exist, open, and a full leak-category re-scan passes.

## Workflow: Inventory → Redact → Re-scan (loop)

1. Extract/search text across **all pages** before any redaction; do not rely on a hand-curated list.
2. Build a leak inventory using detectors and record matches as they appear (surface forms).
3. Expand inventory to include common surface-form variants (protocol-relative URLs, punctuation-suffixed tokens, line breaks/hyphenation).
4. Apply redactions using a scope policy (next section), then save.
5. Re-open the output and re-run the same detectors; repeat redact→save until detectors return empty (or remaining hits are explicitly allowed).
6. After the loop, run corruption/content-retention checks (page count unchanged; substantial text retained).

Read references/leak-inventory-loop.md when you must reliably remove unknown identifiers beyond a provided string list. Skip when the caller supplies an exhaustive leak inventory and a full-document verification scan is already mandated.

## Workflow: Run-continuation gate (tooling + deliverables)

1. Treat every step as **executed only when it ran in a real tool invocation** (terminal / python), not when it was described in chat.
2. If you notice a mis-invocation (pasted JSON, wrong channel, command never ran), immediately retry the same step via a real tool invocation.
3. If any script/tool step errors, fix the error and re-run before doing downstream work.
4. Never end a run while required deliverables are missing; if outputs are missing, return to the loop and produce them.

## Workflow: Scope policy (References-safe)

- **Pre-References scope (typical):** names, affiliations, emails, author homepages/handles, venue/acceptance strings, acknowledgement names.
- **Global scope (exceptions):** identifier classes that must be removed even inside References (e.g., **arXiv IDs/URLs**), plus any other token class explicitly requested as global.

Decision rule: treat “preserve references” as “preserve citations and prose”, not as “block all redactions after References”.

Read references/scope-policy.md when the task both (a) asks to preserve References and (b) calls out identifiers that still must be removed there. Skip when all redactions are explicitly limited to pre-References.

## Operation: Redact exact matches (PyMuPDF)

Use text search to find exact surface forms, add redaction annotations, then apply.

```python
import fitz

def redact_exact(doc: fitz.Document, page_index: int, tokens: list[str]):
    page = doc[page_index]
    for token in tokens:
        for rect in page.search_for(token):
            page.add_redact_annot(rect, fill=(0, 0, 0))
    page.apply_redactions()
```

Decision rule: if a detector finds a hit but `search_for` finds no rectangles, treat it as a surface-form/layout mismatch and switch to a word-level / bbox-derived redaction method.

Read references/word-level-redaction.md when a hit is present in extracted text but `page.search_for()` returns no rectangles. Skip when `search_for()` returns rectangles for all hits.

## Operation: Clear metadata + clean save + re-check

Some PDFs retain prior metadata unless keys are explicitly cleared and the file is rewritten with garbage collection.

```python
import fitz

def scrub_metadata_and_save(doc: fitz.Document, output_path: str):
    meta = dict(doc.metadata or {})
    for k in list(meta.keys()):
        meta[k] = ""
    doc.set_metadata(meta)
    doc.save(output_path, clean=True, garbage=4)


def assert_metadata_empty(path: str):
    d = fitz.open(path)
    meta = d.metadata or {}
    d.close()
    if any((meta.get(k) or "").strip() for k in meta.keys()):
        raise ValueError(f"Metadata not fully cleared: {meta}")
```

Read references/metadata-scrub.md when a PDF keeps title/author/subject/keywords after an initial scrub attempt. Skip when the deliverable is not a PDF file or metadata is out of scope.

## Post-write verification

Before declaring completion:
0. If you notice a tool mis-invocation, **re-run it correctly now**; do not continue with hypothetical results.
1. If any script/tool step failed, **fix the error and re-run using a real tool invocation**; do not proceed as if outputs were produced.
2. Confirm each required output PDF **exists at the required path(s)** and can be opened.
3. Re-scan the written PDF across **all pages** for each leak category the task implies (not just emails/arXiv/metadata).
4. Only when steps 2–3 pass for every deliverable may you stop.

Read references/holistic-verification.md when the task requires “redact all information that could reveal authorship” (or equivalent) and you must prove the output is clean. Skip when the caller provides a fixed set of allowed remaining hits and a checker.

```python
import fitz

def verify_pdf_not_corrupted(original_path: str, output_path: str, min_keep: float = 0.7):
    orig = fitz.open(original_path)
    out = fitz.open(output_path)
    try:
        orig_len = sum(len(p.get_text() or "") for p in orig)
        out_len = sum(len(p.get_text() or "") for p in out)
        if len(orig) != len(out):
            raise ValueError("Page count changed")
        if out_len < 1000:
            raise ValueError("Too little text; possible corruption")
        if orig_len and out_len / orig_len < min_keep:
            raise ValueError("Too much removed")
    finally:
        orig.close(); out.close()
```

## Common Pitfalls

- Declaring done after checking only a subset of leak classes (e.g., emails/arXiv/metadata) instead of a full-category scan that includes affiliations, venues, funding, and author fragments.
- Relying on a fixed string list instead of a full-document detector scan (misses later-page or variant-format leaks).
- Treating “preserve references” as “stop all redactions at References” even when globally-disallowed identifiers must be removed everywhere.
- Clearing metadata with an empty dict and a normal save (some producers persist old fields unless explicitly blanked and rewritten cleanly).
- Assuming `search_for` failures mean “not present” rather than “present but with a different surface form” (spacing, line breaks, punctuation, glyph differences).
- Ending a run while required output files are missing or were never verified as openable.
