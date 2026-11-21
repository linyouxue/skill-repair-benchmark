#!/usr/bin/env python3
"""Academic PDF redaction helper (PyMuPDF).

This script supports the `academic-pdf-redaction` skill:
- Redact *specific* literal matches via `page.search_for()` and redaction annotations.
- Preserve the References section for low-confidence patterns (names/affiliations), while
  still allowing high-confidence deanonymizers (emails, arXiv IDs/URLs, ORCID) to be
  removed globally.
- Clear PDF Info + XMP metadata.
- Remove suspicious URL link annotations (e.g., arXiv/ORCID/mailto) to avoid hidden leaks.
- Verify redaction safety and run a generic leak scan.

IMPORTANT:
- This script is reusable: it does NOT hard-code any task-instance values.
- For regex-based redaction, it first extracts exact matched tokens from each page's
  extracted text and then redacts those literal tokens.
- Note: Extracted-text regex scans do **not** see link targets. This script separately
  inspects PDF link annotations and removes suspicious ones.

Example usage:
  python redact_academic_pdf.py \
    --input input.pdf --output output.pdf \
    --config patterns.json

Config JSON schema (all keys optional):
{
  "pre_ref_literals": ["Full Name", "Institution", "Correspondence:"],
  "global_literals": ["Proceedings of ..."],
  "pre_ref_regexes": ["..."],
  "global_regexes": ["..."],
  "min_retained_ratio": 0.80,
  "redact_dois": false
}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Iterable

# IMPORTANT: We avoid importing PyMuPDF at import-time so the module can be
# linted/loaded even when fitz isn't installed. Import fitz inside functions.


# -------------------------
# References-page detection
# -------------------------


def find_references_start_page(doc) -> int | None:
    """Return 0-based page index where References/Bibliography begins, or None.

    Heuristic: look for a section heading near the top of a page.
    """

    heading_re = re.compile(r"^(?:\d+\s*[\.)]?)?\s*(references|bibliography)\s*$", re.I)

    for pno, page in enumerate(doc):
        lines = [ln.strip() for ln in page.get_text("text").splitlines()[:250] if ln.strip()]
        for ln in lines[:60]:
            if heading_re.match(ln):
                return pno
    return None


# -------------------------
# Metadata handling
# -------------------------

META_KEYS = [
    "title",
    "author",
    "subject",
    "keywords",
    "creator",
    "producer",
    "creationDate",
    "modDate",
    "trapped",
]


def clear_metadata(doc) -> None:
    """Best-effort clearing of Info dictionary and XMP metadata."""

    # Info dictionary
    try:
        doc.set_metadata({k: "" for k in META_KEYS})
    except Exception:
        try:
            doc.set_metadata({})
        except Exception:
            pass

    # XMP metadata (API differs by version)
    for attr in ("set_xml_metadata", "setXmlMetadata"):
        if hasattr(doc, attr):
            try:
                getattr(doc, attr)("")
            except Exception:
                pass


# -------------------------
# Redaction helpers
# -------------------------


def _flags_basic(fitz_module) -> int:
    """Return conservative search flags for literal matching.

    We intentionally do NOT include `TEXT_INHIBIT_SPACES` here.

    In some PyMuPDF versions, setting `TEXT_INHIBIT_SPACES` changes matching
    semantics such that a query containing spaces (e.g., "Duke University") will
    no longer match, while the space-free variant ("DukeUniversity") will.

    To stay predictable, we use basic flags by default and handle whitespace-
    insensitive matching explicitly in `add_redactions_for_literal()`.
    """

    flags = 0
    for name in ("TEXT_IGNORECASE", "TEXT_DEHYPHENATE"):
        flags |= int(getattr(fitz_module, name, 0) or 0)
    return flags


def _flags_inhibit_spaces(fitz_module) -> int:
    """Return flags for whitespace-insensitive matching (best-effort)."""

    flags = _flags_basic(fitz_module)
    flags |= int(getattr(fitz_module, "TEXT_INHIBIT_SPACES", 0) or 0)
    return flags


def _safe_search_for(page, needle: str, *, fitz_module, flags: int | None) -> list:
    """Wrapper around `page.search_for` that is robust across versions."""

    try:
        if flags is None:
            return page.search_for(needle)
        return page.search_for(needle, flags=flags)
    except TypeError:
        # Older PyMuPDF versions may not support `flags=`.
        try:
            return page.search_for(needle)
        except Exception:
            return []
    except Exception:
        return []


def _dedupe_rects(rects) -> list:
    """Deduplicate rectangles by rounded coordinates."""

    out = []
    seen: set[tuple[float, float, float, float]] = set()
    for r in rects or []:
        try:
            key = (
                round(float(r.x0), 2),
                round(float(r.y0), 2),
                round(float(r.x1), 2),
                round(float(r.y1), 2),
            )
        except Exception:
            # If rect doesn't have expected attrs, keep it.
            out.append(r)
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def add_redactions_for_literal(page, text: str, *, fitz_module) -> int:
    """Add redaction annotations for all matches of a literal string.

    This tries both:
    - normal matching (with spaces)
    - whitespace-insensitive matching (space-free query + TEXT_INHIBIT_SPACES),
      when supported

    This makes literal redactions more robust across PDFs where text extraction
    inserts / drops spaces.
    """

    text = (text or "").strip()
    if len(text) < 3:
        return 0

    rects: list = []

    # 1) Normal literal search.
    rects.extend(_safe_search_for(page, text, fitz_module=fitz_module, flags=_flags_basic(fitz_module)))

    # 2) Whitespace-insensitive matching.
    #
    # We always try a compact (space-free) needle with TEXT_INHIBIT_SPACES so we
    # can match PDFs that either:
    # - store text without spaces, or
    # - require space-free queries for whitespace-insensitive search.
    compact = re.sub(r"\s+", "", text)
    if compact and len(compact) >= 3:
        rects.extend(
            _safe_search_for(
                page,
                compact,
                fitz_module=fitz_module,
                flags=_flags_inhibit_spaces(fitz_module),
            )
        )

    rects = _dedupe_rects(rects)

    for r in rects:
        page.add_redact_annot(r, fill=(0, 0, 0))

    return len(rects)


def _normalize_token(tok: str) -> str:
    """Normalize a token extracted from text for safer matching.

    PDF text extraction often introduces line breaks, hyphenation artifacts, and
    surrounding punctuation. We keep this conservative: prefer to under-normalize
    (miss a match) rather than over-normalize (match too broadly).
    """

    tok = (tok or "").strip()

    # Strip common leading/trailing punctuation/brackets/quotes.
    tok = tok.strip("\"'“”‘’()[]{}.,;:!?")

    # Collapse internal whitespace/newlines into a single space.
    tok = re.sub(r"\s+", " ", tok)

    return tok


def _iter_regex_tokens(page_text: str, regexes: Iterable[str]) -> Iterable[str]:
    """Yield candidate literal tokens extracted by regex matches."""

    for rx in regexes:
        for m in re.finditer(rx, page_text, flags=re.I):
            tok = _normalize_token(m.group(0) or "")
            if len(tok) >= 3:
                yield tok


def add_redactions_for_regex_tokens(page, page_text: str, regexes: list[str], *, fitz_module) -> int:
    """Extract tokens by regex from text, then redact them as literals."""

    total = 0
    for tok in dict.fromkeys(_iter_regex_tokens(page_text, regexes)):
        variants = [tok]

        # Help catch scheme-less arXiv links and common variants.
        low = tok.lower()
        if "arxiv.org/abs" in low or "arxiv.org/pdf" in low:
            stripped = tok.lstrip("/")
            variants.extend([
                "https://" + stripped,
                "http://" + stripped,
                "//" + stripped,
            ])

        # Common punctuation/whitespace variants.
        variants.extend([
            tok.rstrip(".") + ".",
            tok.rstrip("."),
            tok.replace(" ", ""),
        ])

        for v in dict.fromkeys(_normalize_token(v) for v in variants if v and len(v.strip()) >= 3):
            if len(v) >= 3:
                total += add_redactions_for_literal(page, v, fitz_module=fitz_module)

            # Extra robustness: also try a space-free form. Some PDFs store
            # tokens without spaces while extracted text contains spaces (or vice
            # versa). `add_redactions_for_literal()` already has a similar
            # fallback, but calling this here helps when the variant list itself
            # introduces whitespace.
            v_compact = re.sub(r"\s+", "", v)
            if v_compact and v_compact != v and len(v_compact) >= 3:
                total += add_redactions_for_literal(page, v_compact, fitz_module=fitz_module)

    return total


# -------------------------
# Link annotation handling
# -------------------------


def _iter_external_link_targets(doc) -> list[str]:
    """Return a list of external link targets (URIs/files) in the document.

    Note: These targets are not necessarily present in extracted text.
    """

    targets: list[str] = []
    for page in doc:
        try:
            links = page.get_links() or []
        except Exception:
            continue
        for lnk in links:
            # External link types typically include `uri` (web/mailto) or `file`.
            uri = lnk.get("uri")
            if uri:
                targets.append(str(uri))
            file = lnk.get("file")
            if file:
                targets.append(str(file))
    return targets


def _delete_link_best_effort(page, link: dict) -> bool:
    """Delete a link annotation using whatever API is available."""

    if hasattr(page, "delete_link"):
        try:
            page.delete_link(link)
            return True
        except Exception:
            pass

    # Fallback: delete the underlying annotation by xref if available.
    xref = link.get("xref")
    if xref and hasattr(page, "load_annot") and hasattr(page, "delete_annot"):
        try:
            annot = page.load_annot(xref)
            if annot:
                page.delete_annot(annot)
                return True
        except Exception:
            pass

    return False


def remove_external_links(doc) -> int:
    """Remove external link annotations (URIs/files) in-place.

    We keep internal navigation links (page jumps) intact, but strip links that can
    embed deanonymizing URLs even when the visible text is already redacted.
    """

    removed = 0
    for page in doc:
        try:
            links = page.get_links() or []
        except Exception:
            continue
        for lnk in list(links):
            if lnk.get("uri") or lnk.get("file"):
                if _delete_link_best_effort(page, lnk):
                    removed += 1
    return removed


# -------------------------
# Verification / leak scan
# -------------------------


def verify_redaction(original_path: str, output_path: str, *, min_retained_ratio: float = 0.80) -> None:
    import fitz  # type: ignore

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


DEFAULT_GLOBAL_LEAK_REGEXES = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",

    # arXiv identifiers (new + legacy forms)
    # - arXiv:2301.01234v2
    # - arXiv:cs.CL/9901001
    r"\barxiv\s*:\s*(?:\d{4}\.\d{4,5}(?:v\d+)?|[A-Za-z\-]+(?:\.[A-Za-z]{2})?/\d{7}(?:v\d+)?)\b",

    # arXiv URLs (match even when only the prefix is present)
    r"(?:https?:)?//(?:www\.)?arxiv\.org/(?:abs|pdf)/\S*",
    r"\b(?:www\.)?arxiv\.org/(?:abs|pdf)/\S*",
    r"\barxiv\.org/(?:abs|pdf)/\S*",

    # Misc common identifiers
    r"\b\d{4}-\d{4}-\d{4}-\d{3}[0-9X]\b",  # ORCID-like

    # Generic but high-confidence identifier types for author de-anonymization
    r"\bORCID\b",
]

DEFAULT_DOI_REGEX = r"\b10\.\d{4,9}/[^\s)\],;]+"


def scan_for_common_leaks(
    pdf_path: str,
    *,
    extra_regexes: list[str] | None = None,
    check_external_links: bool = True,
) -> None:
    """Fail fast if obvious deanonymizers remain (best-effort).

    This checks:
    - extracted text (emails, arXiv IDs/URLs, ORCID-like patterns)
    - PDF Info + XMP metadata
    - (optionally) external link annotations (URIs/files) that may contain URLs
      not present in extracted text.
    """

    import fitz  # type: ignore

    doc = fitz.open(pdf_path)
    text = "\n".join(p.get_text("text") for p in doc)

    link_targets: list[str] = []
    if check_external_links:
        link_targets = _iter_external_link_targets(doc)

    regexes = list(DEFAULT_GLOBAL_LEAK_REGEXES)
    if extra_regexes:
        regexes.extend(extra_regexes)

    hits = [rx for rx in regexes if re.search(rx, text, flags=re.I)]

    # Info metadata checks
    meta = doc.metadata or {}
    nonempty_info = {k: v for k, v in meta.items() if v and k not in ("format",)}

    # XMP metadata checks
    xmp = ""
    for attr in ("get_xml_metadata", "getXmlMetadata"):
        if hasattr(doc, attr):
            try:
                xmp = getattr(doc, attr)() or ""
            except Exception:
                pass

    doc.close()

    if nonempty_info:
        raise ValueError(f"Non-empty PDF Info metadata remains: {nonempty_info}")
    if xmp and xmp.strip():
        raise ValueError("XMP metadata remains non-empty; clear it to avoid identity leaks")

    if link_targets:
        suspicious_link_rxes = [
            r"\barxiv\.org/",  # arXiv URLs
            r"\borcid\.org/",  # ORCID URLs
            r"mailto:",
        ]
        link_hits = [
            t
            for t in link_targets
            if any(re.search(rx, t, flags=re.I) for rx in suspicious_link_rxes)
        ]
        if link_hits:
            raise ValueError(f"Potential deanonymizing external link targets remain: {link_hits[:10]}")

    if hits:
        raise ValueError(f"Potential leak patterns still present: {hits}")


# -------------------------
# CLI
# -------------------------


@dataclass
class PatternConfig:
    pre_ref_literals: list[str]
    global_literals: list[str]
    pre_ref_regexes: list[str]
    global_regexes: list[str]
    min_retained_ratio: float
    redact_dois: bool


def _as_list(x: Any) -> list[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(v) for v in x]
    raise TypeError("Expected a list")


def load_config(path: str | None) -> PatternConfig:
    data: dict[str, Any] = {}
    if path:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}

    min_retained_ratio = float(data.get("min_retained_ratio", 0.80))
    if not (0.0 < min_retained_ratio <= 1.0):
        raise ValueError("min_retained_ratio must be in (0, 1]")

    redact_dois = bool(data.get("redact_dois", False))

    return PatternConfig(
        pre_ref_literals=_as_list(data.get("pre_ref_literals")),
        global_literals=_as_list(data.get("global_literals")),
        pre_ref_regexes=_as_list(data.get("pre_ref_regexes")),
        global_regexes=_as_list(data.get("global_regexes")),
        min_retained_ratio=min_retained_ratio,
        redact_dois=redact_dois,
    )


def redact_pdf(
    *,
    input_path: str,
    output_path: str,
    cfg: PatternConfig,
    extra_pre_ref_literals: list[str],
    extra_global_literals: list[str],
    add_default_leak_regexes: bool,
    verify: bool,
    scan: bool,
) -> None:
    import fitz  # type: ignore

    doc = fitz.open(input_path)
    clear_metadata(doc)

    # Remove external link annotations (URLs may remain even if the visible text
    # is redacted and extracted-text scans look clean).
    remove_external_links(doc)

    ref_start = find_references_start_page(doc)

    # Build pattern sets
    pre_ref_literals = [*cfg.pre_ref_literals, *extra_pre_ref_literals]
    global_literals = [*cfg.global_literals, *extra_global_literals]

    pre_ref_regexes = list(cfg.pre_ref_regexes)
    global_regexes = list(cfg.global_regexes)

    if cfg.redact_dois:
        global_regexes.append(DEFAULT_DOI_REGEX)

    if add_default_leak_regexes:
        global_regexes.extend(DEFAULT_GLOBAL_LEAK_REGEXES)

    for pno, page in enumerate(doc):
        page_text = page.get_text("text")

        # Always-on redactions
        for s in global_literals:
            add_redactions_for_literal(page, s, fitz_module=fitz)
        add_redactions_for_regex_tokens(page, page_text, global_regexes, fitz_module=fitz)

        # Pre-References-only redactions
        if ref_start is None or pno < ref_start:
            for s in pre_ref_literals:
                add_redactions_for_literal(page, s, fitz_module=fitz)
            add_redactions_for_regex_tokens(page, page_text, pre_ref_regexes, fitz_module=fitz)

        page.apply_redactions()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()

    if verify:
        verify_redaction(input_path, output_path, min_retained_ratio=cfg.min_retained_ratio)
    if scan:
        scan_for_common_leaks(output_path, check_external_links=True)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Redact academic PDFs for blind review (PyMuPDF).")
    p.add_argument("--input", required=True, help="Input PDF path")
    p.add_argument("--output", required=True, help="Output PDF path")
    p.add_argument("--config", help="JSON config with pattern lists")

    p.add_argument("--pre-ref-literal", action="append", default=[], help="Literal to redact before References")
    p.add_argument("--global-literal", action="append", default=[], help="Literal to redact on all pages")

    p.add_argument(
        "--no-default-leak-regexes",
        action="store_true",
        help="Do not automatically include default leak regexes (emails/arXiv/ORCID)",
    )
    p.add_argument("--verify", action="store_true", default=True, help="Verify output safety (default on)")
    p.add_argument("--no-verify", action="store_true", help="Disable verification")
    p.add_argument("--scan", action="store_true", default=True, help="Run leak scan (default on)")
    p.add_argument("--no-scan", action="store_true", help="Disable leak scan")

    args = p.parse_args(argv)

    cfg = load_config(args.config)

    verify = bool(args.verify) and not bool(args.no_verify)
    scan = bool(args.scan) and not bool(args.no_scan)

    redact_pdf(
        input_path=args.input,
        output_path=args.output,
        cfg=cfg,
        extra_pre_ref_literals=list(args.pre_ref_literal or []),
        extra_global_literals=list(args.global_literal or []),
        add_default_leak_regexes=not bool(args.no_default_leak_regexes),
        verify=verify,
        scan=scan,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
