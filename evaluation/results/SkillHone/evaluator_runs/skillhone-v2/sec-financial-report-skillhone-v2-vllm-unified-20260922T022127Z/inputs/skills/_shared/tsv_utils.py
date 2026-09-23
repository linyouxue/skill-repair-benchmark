"""Small TSV utilities (stdlib-only).

We intentionally avoid heavyweight dependencies (pandas, rapidfuzz) because the
SkillHone runtime for this benchmark may not ship them.

All functions here are streaming-friendly and operate on UTF-8 TSV files.
"""

from __future__ import annotations

import csv
import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, Iterator, List, Optional, Tuple


def iter_tsv(path: str) -> Iterator[Dict[str, str]]:
    """Yield rows from a TSV as dicts."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # normalize None -> "" to simplify downstream
            yield {k: (v if v is not None else "") for k, v in row.items()}


_ws_re = re.compile(r"\s+")
_non_alnum_re = re.compile(r"[^a-z0-9 ]+")


def normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = _non_alnum_re.sub(" ", s)
    s = _ws_re.sub(" ", s).strip()
    return s


def fuzzy_score(query: str, choice: str) -> float:
    """Return a 0..100 fuzzy score using stdlib SequenceMatcher.

    This is not identical to rapidfuzz.WRatio but works well enough for
    manager/issuer name matching.
    """
    q = normalize_text(query)
    c = normalize_text(choice)
    if not q or not c:
        return 0.0
    return 100.0 * SequenceMatcher(None, q, c).ratio()


def topk_fuzzy(query: str, choices: Iterable[str], k: int = 10) -> List[Tuple[str, float]]:
    scored: List[Tuple[str, float]] = []
    for ch in choices:
        scored.append((ch, fuzzy_score(query, ch)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[: max(0, int(k))]


def safe_float(s: str, default: float = 0.0) -> float:
    try:
        return float(s)
    except Exception:
        return default
