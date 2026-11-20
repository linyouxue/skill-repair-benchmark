"""Reusable text-mining helpers for OCR output of printed documents.

Everything in this module is intentionally generic:

* ``parse_date_candidates`` finds day/month/year patterns and returns ISO
  strings. You decide the day-first vs month-first preference per call.
* ``find_money_values`` extracts decimal monetary numbers (``.`` or ``,``
  decimal separator, optional thousands separator).
* ``extract_by_priority`` implements the standard "keyword tier" lookup
  commonly used on receipts, invoices and similar documents. Callers supply
  their own tier list and exclusion list, so no concrete keyword table is
  hard-coded here.

No task-specific keywords, output filenames, dataset paths, column names
or answers appear in this module. It is meant to be imported by the
agent's task-specific extraction script.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- #
# Numeric helpers
# --------------------------------------------------------------------------- #

# Matches 123.45, 1,234.56, 12.3 and friends. Lookbehind/ahead keep us from
# chopping larger numbers or sticking to adjacent letters.
_MONEY_RE = re.compile(
    r"(?<![\w.])"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:[.,]\d{1,2})?|\d+[.,]\d{1,2}|\d+)"
    r"(?![\w.])",
)

# Common OCR substitutions seen in numeric columns. Keep this conservative —
# only characters that are visually identical to digits on printed receipts.
_OCR_DIGIT_FIX = str.maketrans({
    "O": "0", "o": "0", "D": "0", "Q": "0",
    "l": "1", "I": "1", "|": "1",
    "S": "5", "s": "5",
    "B": "8",
    "Z": "2",
    "g": "9", "q": "9",
})


def normalize_ocr_digits(token: str) -> str:
    """Return *token* with common letter-for-digit confusions fixed."""
    return token.translate(_OCR_DIGIT_FIX)


def _to_decimal(raw: str, require_decimal: bool) -> Optional[float]:
    """Parse a money-like token to float. Return ``None`` on failure."""
    s = raw.replace(" ", "")
    if "." in s and "," in s:
        # Assume comma is a thousands separator when both appear.
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        # Either thousands or a European decimal. 1,234 vs 12,34 — disambiguate
        # by the number of fractional digits.
        tail = s.rsplit(",", 1)[1]
        if len(tail) == 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    if require_decimal and "." not in s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def find_money_values(line: str, require_decimal: bool = True) -> List[float]:
    """Return every monetary number found in *line*, in order."""
    out: List[float] = []
    for m in _MONEY_RE.finditer(line):
        val = _to_decimal(m.group("num"), require_decimal=require_decimal)
        if val is not None:
            out.append(val)
    return out


def last_money_value(line: str, require_decimal: bool = True) -> Optional[float]:
    vals = find_money_values(line, require_decimal=require_decimal)
    return vals[-1] if vals else None


def format_money(value: float, decimals: int = 2) -> str:
    """Return *value* formatted as plain ``"N.MM"`` with trailing zeros."""
    return f"{value:.{decimals}f}"


# --------------------------------------------------------------------------- #
# Date helpers
# --------------------------------------------------------------------------- #

# D/M/Y, D-M-Y, D.M.Y. Accepts 2- or 4-digit year. Each component is bounded
# by a non-word character so numeric amounts in nearby text do not match.
_DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})[\s./\-](\d{1,2})[\s./\-](\d{2,4})(?!\d)",
)

# Y-M-D form, usually preferred when it appears.
_ISO_DATE_RE = re.compile(
    r"(?<!\d)(\d{4})[\s./\-](\d{1,2})[\s./\-](\d{1,2})(?!\d)",
)


def _year_to_full(y: int) -> int:
    if y < 100:
        # Pivot around 2000. Receipt dates are nearly always recent.
        return 2000 + y if y < 70 else 1900 + y
    return y


def _try_date(y: int, m: int, d: int) -> Optional[str]:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_date_candidates(text: str, day_first: bool = True) -> List[str]:
    """Return all parseable ISO dates found in *text*.

    When *day_first* is ``True`` the ``a/b/c`` form is tried as D/M/Y first,
    and M/D/Y is used only as a fallback when the day-first interpretation
    is out of range.
    """
    found: List[str] = []
    for m in _ISO_DATE_RE.finditer(text):
        y, mo, d = (int(m.group(i)) for i in (1, 2, 3))
        iso = _try_date(y, mo, d)
        if iso:
            found.append(iso)
    for m in _DATE_RE.finditer(text):
        a, b, c = (int(m.group(i)) for i in (1, 2, 3))
        y = _year_to_full(c)
        order = ((a, b), (b, a)) if day_first else ((b, a), (a, b))
        for day, month in order:
            iso = _try_date(y, month, day)
            if iso:
                found.append(iso)
                break
    return found


def pick_best_date(candidates: Sequence[str]) -> Optional[str]:
    """Pick the most common date from *candidates*; ties go to the first."""
    if not candidates:
        return None
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c] = counts.get(c, 0) + 1
    best = max(counts.items(), key=lambda kv: (kv[1], -candidates.index(kv[0])))
    return best[0]


# --------------------------------------------------------------------------- #
# Priority-tier keyword extraction
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class KeywordTier:
    """One tier of keywords to look for, with a human label.

    Each pattern is a raw regex string. Patterns are compiled with
    ``re.IGNORECASE`` and matched against each line as written (callers
    should pre-normalise punctuation if they need extra flexibility).
    """
    name: str
    patterns: Tuple[str, ...]


@dataclass
class Candidate:
    """One possible extracted value from a line."""
    tier_index: int
    tier_name: str
    line_index: int
    line_text: str
    value: float


def _compile_patterns(patterns: Iterable[str]) -> List[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def _line_matches(patterns: Sequence[re.Pattern], line: str) -> bool:
    return any(p.search(line) for p in patterns)


def extract_by_priority(
    text: str,
    tiers: Sequence[KeywordTier],
    exclusion_patterns: Sequence[str] = (),
    *,
    section_break_patterns: Sequence[str] = (),
    fallback_next_lines: int = 1,
    require_decimal: bool = True,
) -> Optional[Candidate]:
    """Find the best monetary candidate using a priority-tier scheme.

    Rules, in order:

    1. Iterate *tiers* from most to least specific.
    2. Within each tier, iterate matching, non-excluded lines **in reverse**
       (receipts tend to put the final total last).
    3. If the matched line contains a usable money value, return it.
    4. Otherwise, only if the matched line has NO digits at all, fall back
       to the next ``fallback_next_lines`` non-excluded lines and use the
       last money value on them. Lines with digits but no decimal are
       treated as corrupt and are skipped without triggering the fallback —
       this avoids picking up unrelated "Visa RM 688.17" style lines.
    5. Lines after a *section_break_pattern* match (e.g. a "GST summary"
       header) are ignored to avoid tax-summary tables.

    Returns the chosen :class:`Candidate` or ``None`` when nothing matches.
    """
    compiled_tiers = [(t, _compile_patterns(t.patterns)) for t in tiers]
    excl = _compile_patterns(exclusion_patterns)
    breaks = _compile_patterns(section_break_patterns)

    raw_lines = text.splitlines()
    # Drop lines after a section-break match.
    cutoff = len(raw_lines)
    for i, line in enumerate(raw_lines):
        if _line_matches(breaks, line):
            cutoff = i
            break
    lines = raw_lines[:cutoff]

    def is_excluded(line: str) -> bool:
        return _line_matches(excl, line)

    def has_digit(line: str) -> bool:
        return any(ch.isdigit() for ch in line)

    for tier_idx, (tier, patterns) in enumerate(compiled_tiers):
        candidates = [
            i for i, line in enumerate(lines)
            if _line_matches(patterns, line) and not is_excluded(line)
        ]
        for i in reversed(candidates):
            line = lines[i]
            val = last_money_value(line, require_decimal=require_decimal)
            if val is not None:
                return Candidate(tier_idx, tier.name, i, line, val)
            if has_digit(line):
                # Corrupt amount on the same line — do not fall through.
                continue
            # Pure keyword line: look at the next ``fallback_next_lines`` lines.
            for j in range(i + 1, min(i + 1 + fallback_next_lines, len(lines))):
                if not lines[j].strip():
                    continue
                if is_excluded(lines[j]):
                    break
                val = last_money_value(lines[j], require_decimal=require_decimal)
                if val is not None:
                    return Candidate(tier_idx, tier.name, j, lines[j], val)
                break
    return None


def vote_candidates(candidates: Sequence[Candidate]) -> Optional[Candidate]:
    """Pick the best candidate across OCR variants.

    Scoring, higher is better:

    * Prefer the smallest ``tier_index`` (most specific keyword).
    * Within the same tier, prefer the *value* that appears most often.
    * Ties fall back to the first occurrence.
    """
    if not candidates:
        return None
    best_tier = min(c.tier_index for c in candidates)
    pool = [c for c in candidates if c.tier_index == best_tier]
    counts: dict[float, int] = {}
    for c in pool:
        counts[c.value] = counts.get(c.value, 0) + 1
    best_value = max(counts.items(), key=lambda kv: kv[1])[0]
    for c in pool:
        if c.value == best_value:
            return c
    return pool[0]


__all__ = [
    "Candidate",
    "KeywordTier",
    "extract_by_priority",
    "find_money_values",
    "format_money",
    "last_money_value",
    "normalize_ocr_digits",
    "parse_date_candidates",
    "pick_best_date",
    "vote_candidates",
]
