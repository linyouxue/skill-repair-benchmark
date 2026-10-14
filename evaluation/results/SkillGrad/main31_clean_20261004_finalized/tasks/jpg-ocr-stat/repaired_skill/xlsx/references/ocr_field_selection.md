# OCR field selection for spreadsheet outputs (dates, totals, IDs)

Use this when you must populate spreadsheet rows from OCR text and the document can contain multiple plausible candidates per field (e.g., several dates, subtotal/tax/total/change, IDs that look numeric).

## Goal

Avoid brittle “first regex match” or “last number on a line” heuristics by (1) generating multiple candidates, (2) applying a prompt-faithful *priority search* (for totals), (3) enforcing *absolute exclusions* (no “TOTAL overrides GST/TAX”), and (4) returning null when evidence is weak or ambiguous.

## Procedure (branched)

```python
import re
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Candidate:
    kind: str
    value: str
    line_idx: int
    start: int
    context: str

money_re = re.compile(r"(?<!\w)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?(?!\w)")
date_res = [
    re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"),
    re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"),
]

def normalize_lines(text: str) -> list[str]:
    raw = [ln.strip() for ln in text.splitlines()]
    return [re.sub(r"\s+", " ", ln) for ln in raw if ln.strip()]

def collect_candidates(lines: list[str]) -> list[Candidate]:
    out: list[Candidate] = []
    for i, ln in enumerate(lines):
        for dr in date_res:
            for m in dr.finditer(ln):
                out.append(Candidate("date", m.group(0), i, m.start(), ln))
        for m in money_re.finditer(ln):
            out.append(Candidate("money", m.group(0), i, m.start(), ln))
    return out
```

### Branch A — Selecting totals (priority search + absolute exclusions)

Do not let generic scoring override intent. Instead, search in strict priority order and *reject* excluded contexts at every step.

**Absolute exclusions (apply to every priority group)**
Reject any candidate whose local window contains any of:
- GST, SST, VAT, TAX
- SUMMARY

Also treat these as strong negatives (typically reject unless the prompt explicitly allows):
- SUBTOTAL, ROUNDING, DISCOUNT, ADJ/ADJUST
- CASH/PAID/TENDERED/CHANGE/CARD
- QTY/ITEMS, INVOICE/RECEIPT NO/REF/AUTH/ID
- table header terms like DESCRIPTION / AMOUNT / PRICE / TOTAL as a column label

```python
from typing import Optional

POS_1 = ["grand total", "total amount", "amount due", "balance due"]
POS_2 = ["total rm", "total: rm", "total (rm)", "total rounded"]
POS_3 = ["total"]

ABS_NEG = ["gst", "sst", "vat", "tax", "summary"]
STRONG_NEG = [
    "subtotal", "rounding", "discount", "adjust", "adj",
    "cash", "paid", "tender", "change", "card",
    "qty", "items", "invoice", "receipt no", "ref", "auth", " id",
    "description", "price",  # table-like contexts
]


def _window(lines: list[str], i: int, k: int = 1) -> str:
    return " ".join(lines[max(0, i-k):min(len(lines), i+k+1)]).lower()


def _has_strict_money_token(s: str) -> bool:
    return bool(re.search(r"(?<!\w)\d+(?:,\d{3})*\.\d{2}(?!\w)", s))


def pick_total_amount(lines: list[str]) -> Optional[str]:
    # bottom-most wins inside a priority group (receipts often repeat totals)
    for group in (POS_1, POS_2, POS_3):
        for i in range(len(lines) - 1, -1, -1):
            win = _window(lines, i, k=1)
            if any(n in win for n in ABS_NEG):
                continue
            if any(k in win for k in group):
                if any(n in win for n in STRONG_NEG):
                    continue
                if _has_strict_money_token(lines[i]):
                    m = re.search(r"\d+(?:,\d{3})*\.\d{2}", lines[i])
                    return m.group(0) if m else None
                # scan-forward only to capture wrapped totals; keep context = keyword line
                for j in range(i + 1, min(len(lines), i + 5)):
                    if any(n in _window(lines, j, k=1) for n in ABS_NEG):
                        break
                    if _has_strict_money_token(lines[j]):
                        m = re.search(r"\d+(?:,\d{3})*\.\d{2}", lines[j])
                        return m.group(0) if m else None
    return None
```

Runtime branch: if `pick_total_amount` returns `None`, fall back to candidate scoring *but keep absolute exclusions mandatory* and require a null-on-ambiguity margin.

### Branch B — Selecting dates (conservative normalization + null on ambiguity)

Only normalize OCR confusions when you already have a date-like token, and reject results that don’t parse cleanly.

```python
import re
from typing import Optional


def normalize_date_token(token: str) -> str:
    # only apply to date-like strings; keep it minimal to avoid inventing a new date
    t = token.strip()
    t = re.sub(r"\s+", "", t)
    t = t.replace("O", "0").replace("o", "0")
    return t


def parse_date_or_null(token: str) -> Optional[str]:
    t = normalize_date_token(token)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            dt = datetime.strptime(t, fmt)
            if not (2000 <= dt.year <= 2100):
                return None
            return dt.date().isoformat()
        except ValueError:
            pass
    return None
```

Runtime branch: if multiple date candidates parse and none has strong context (e.g., TRANSACTION/DATE) or the top-2 scores are close, output null rather than choosing by position.

## Null-on-ambiguity policy (required when spec allows null)

```python
from typing import Optional

def pick_best_or_null(scored: list[tuple[Candidate, float]], margin: float = 1.0, min_score: float = 2.0) -> Optional[Candidate]:
    if not scored:
        return None
    scored = sorted(scored, key=lambda t: t[1], reverse=True)
    (c1, s1) = scored[0]
    s2 = scored[1][1] if len(scored) > 1 else float("-inf")

    if s1 < min_score:
        return None
    if (s1 - s2) < margin:
        return None
    return c1
```

## Verification and corrective action

- Verify: for every non-null total/date, assert the source context window does **not** contain any absolute exclusion tokens (GST/SST/VAT/TAX/SUMMARY).
- If verification fails: tighten the window (keyword line + neighbors), expand the absolute exclusion list, and re-run extraction end-to-end.
- If many totals/dates become null: adjust *rules* (priority phrases, scan-forward limit, year range) and re-run; do not “guess-fill” nulls unless explicitly allowed.
