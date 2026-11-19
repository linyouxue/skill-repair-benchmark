#!/usr/bin/env python3
"""skills/xlsx/entity_keys.py

Dependency-free helpers for normalizing entity names from spreadsheet headers.

Why this exists
---------------
Many economic/financial spreadsheets store time series in a *wide* format where
columns are entities (countries, firms, products, etc.) and the header text is
noisy, e.g.:

  "Entity: Indicator: Units (notes)"
  "Entity Intl Something: ..."
  "Entity International Something (notes)"

When you need to:
- union entities across multiple sheets,
- de-duplicate entities,
- or look up an entity across sheets,

naively splitting on ':' can produce mismatches (abbreviations, extra
qualifiers like "... reserves", punctuation/whitespace differences).

This module provides small, conservative normalization utilities:
- `extract_entity_label()` returns a cleaned display label.
- `entity_key()` returns a canonical key for matching/dedup (case-insensitive).
- `dedupe_preserve_order()` de-dupes while keeping the first occurrence.

Stdlib only (safe to use in constrained environments).

NOTE: These heuristics are intentionally lightweight. If your dataset has
edge cases, prefer supplying your own explicit mapping table.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable, Iterable, List, Sequence, Tuple, TypeVar

T = TypeVar("T")


_ABBREV_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    # Common abbreviations that frequently vary across sheets.
    (re.compile(r"\bint'l\b", flags=re.IGNORECASE), "international"),
    (re.compile(r"\bintl\b", flags=re.IGNORECASE), "international"),
]

# Phrases that often appear after the entity name in some series headers.
# If present, we truncate the label before the phrase.
_TRUNCATE_PHRASES = [
    "international reserves",
    "foreign reserves",
    "official reserve assets",
    "official foreign reserves",
    "reserve assets",
    "total reserves",
]


def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00a0", " ")  # NBSP
    s = s.strip()
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def extract_entity_label(header: str | None) -> str:
    """Extract a human-readable entity label from a column header.

    Heuristics (in order):
    - Normalize unicode/whitespace.
    - Use the substring before the first ':' if present.
    - Strip trailing parenthetical notes.
    - Expand a small set of abbreviations.
    - Truncate before common trailing descriptor phrases.

    Returns an empty string if header is falsy.
    """

    if not header:
        return ""

    s = _norm_text(str(header))

    # Take the part before the first ':' when present.
    if ":" in s:
        s = s.split(":", 1)[0].strip()

    # Strip trailing "( ... )" notes.
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()

    # Expand common abbreviations.
    for pat, repl in _ABBREV_REPLACEMENTS:
        s = pat.sub(repl, s)

    s = _norm_text(s)

    # Truncate before common trailing descriptor phrases.
    lower = s.lower()
    for phrase in _TRUNCATE_PHRASES:
        idx = lower.find(phrase)
        if idx > 0:
            s = s[:idx].strip()
            break

    return s


def entity_key(header_or_label: str | None) -> str:
    """Return a canonical key for matching/deduplicating entities.

    This is a *lossy* transformation intended for joins, not display.
    """

    label = extract_entity_label(header_or_label)
    label = label.lower()
    # Drop punctuation/whitespace for robust joins.
    label = re.sub(r"[^a-z0-9]+", "", label)
    return label


def dedupe_preserve_order(items: Sequence[T], *, key: Callable[[T], str]) -> List[T]:
    """Return a list with duplicates removed, preserving first-seen order."""

    seen: set[str] = set()
    out: List[T] = []
    for it in items:
        k = key(it)
        if not k:
            continue
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def _demo(argv: Sequence[str]) -> int:
    if not argv:
        print("Usage: entity_keys.py <header1> [<header2> ...]")
        return 2

    for h in argv:
        print(f"raw:   {h}")
        print(f"label: {extract_entity_label(h)}")
        print(f"key:   {entity_key(h)}")
        print("---")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_demo(sys.argv[1:]))
