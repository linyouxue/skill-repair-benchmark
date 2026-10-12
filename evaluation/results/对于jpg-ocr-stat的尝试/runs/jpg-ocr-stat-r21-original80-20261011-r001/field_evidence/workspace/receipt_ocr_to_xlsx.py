from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pytesseract
from PIL import Image, ImageFilter, ImageOps
from openpyxl import Workbook


IMG_DIR = Path("/app/workspace/dataset/img")
OUT_XLSX = Path("/app/workspace/stat_ocr.xlsx")


HARD_EXCLUSION_KEYWORDS = [
    "SUBTOTAL",
    "SUB TOTAL",
    "DISCOUNT",
    "CHANGE",
    "CASH TENDERED",
    "GST SUMMARY",
    "SUMMARY AMOUNT",
]

SOFT_EXCLUSION_KEYWORDS = [
    "TAX",
    "GST",
    "SST",
]

PRIORITY_KEYWORDS = [
    ["GRAND TOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    [
        "TOTAL DUE",
        "AMOUNT DUE",
        "BALANCE DUE",
        "NETT TOTAL",
        "NET TOTAL",
        "TOTAL",
        "AMOUNT",
    ],
]

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "SEPT": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def _normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _prep_image(img: Image.Image, invert: bool = False, sharpen: bool = True) -> Image.Image:
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    if min(img.size) < 900:
        img = img.resize((img.size[0] * 2, img.size[1] * 2))
    if invert:
        img = ImageOps.invert(img)
    if sharpen:
        img = img.filter(ImageFilter.SHARPEN)
    return img


def ocr_text(path: Path, invert: bool = False, sharpen: bool = True) -> list[str]:
    img = _prep_image(Image.open(path), invert=invert, sharpen=sharpen)
    cfg = "--oem 1 --psm 6"
    txt = pytesseract.image_to_string(img, lang="eng", config=cfg)
    lines = [_normalize_spaces(ln) for ln in txt.splitlines()]
    return [ln for ln in lines if ln]


_amount_token_re = re.compile(
    r"(?<!\d)([-+]?\d{1,3}(?:,\d{3})*|[-+]?\d+)(?:\s*[\.,]\s*(\d{1,2}))?(?!\d)"
)


def _parse_amount_token(raw: str) -> Decimal | None:
    s = raw.strip()
    s = re.sub(r"(?<=\d)\s*([\.,])\s*(?=\d)", r"\1", s)

    if s.count(",") and s.count("."):
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        # Might be decimal comma (73,40) or thousands (1,234)
        if re.fullmatch(r"[-+]?\d+,\d{2}", s):
            s = s.replace(",", ".")
        elif re.fullmatch(r"[-+]?\d{1,3}(?:,\d{3})+", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", "")

    try:
        d = Decimal(s)
    except InvalidOperation:
        return None

    # Receipts totals should be non-negative
    if d < 0:
        return None
    return d


def amounts_in_line(line: str) -> list[Decimal]:
    cleaned = line.upper().replace("RM", " ")
    out: list[Decimal] = []
    for m in _amount_token_re.finditer(cleaned):
        a, b = m.group(1), m.group(2)
        tok = a if b is None else f"{a}.{b}"
        d = _parse_amount_token(tok)
        if d is not None:
            out.append(d)
    return out


def _format_money(d: Decimal) -> str:
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{q:.2f}"


def _has_hard_exclusion(u: str) -> bool:
    return any(k in u for k in HARD_EXCLUSION_KEYWORDS)


def _has_soft_exclusion(u: str) -> bool:
    return any(k in u for k in SOFT_EXCLUSION_KEYWORDS)


def _is_table_header_total(u: str) -> bool:
    if "QTY" in u and "ITEM" in u and "TOTAL" in u:
        return True
    if "ITEM TOTAL" in u:
        return True
    if "TOTAL SAVING" in u or "TOTAL SAVINGS" in u:
        return True
    return False


def extract_total_amount(lines: list[str]) -> str | None:
    ulines = [ln.upper() for ln in lines]

    for allow_soft_exclusions in (False, True):
        for group_idx, group in enumerate(PRIORITY_KEYWORDS):
            for i, (ln, u) in enumerate(zip(lines, ulines)):
                if _has_hard_exclusion(u) or _is_table_header_total(u):
                    continue
                if not allow_soft_exclusions and _has_soft_exclusion(u):
                    continue
                if not any(k in u for k in group):
                    continue

                amts = amounts_in_line(ln)
                if amts:
                    return _format_money(amts[-1])

                allow_next = group_idx <= 2
                if not allow_next:
                    s = u.strip()
                    allow_next = bool(re.fullmatch(r"(TOTAL|AMOUNT)\s*[:\-]?", s)) or any(
                        q in u
                        for q in (
                            "RM",
                            ":",
                            "DUE",
                            "ROUNDED",
                            "NET",
                            "PAYABLE",
                            "(RM",
                        )
                    )

                if not allow_next:
                    continue

                for j in range(i + 1, min(i + 3, len(lines))):
                    if not lines[j].strip():
                        continue
                    uj = ulines[j]
                    if _has_hard_exclusion(uj):
                        continue
                    if not allow_soft_exclusions and _has_soft_exclusion(uj):
                        continue
                    amts2 = amounts_in_line(lines[j])
                    if amts2:
                        return _format_money(amts2[-1])

    # Fallback: bottom-up scan, still skipping hard/soft exclusions
    for i in range(len(lines) - 1, -1, -1):
        u = ulines[i]
        if _has_hard_exclusion(u) or _has_soft_exclusion(u):
            continue
        amts = amounts_in_line(lines[i])
        if amts:
            return _format_money(amts[-1])

    return None


_numeric_date_re = re.compile(r"\b(\d{1,4})[\-/\.](\d{1,2})[\-/\.](\d{1,4})\b")
_monthname_re = re.compile(
    r"\b(\d{1,2})\s*[-/\.]?\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)\s*[-/\.]?\s*(\d{2,4})\b",
    re.IGNORECASE,
)
_monthname_re2 = re.compile(
    r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)\s*(\d{1,2})\s*,?\s*(\d{2,4})\b",
    re.IGNORECASE,
)


def _pivot_year(y: int) -> int:
    if y < 100:
        return 2000 + y if y < 70 else 1900 + y
    return y


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


@dataclass(frozen=True)
class DateCandidate:
    score: float
    idx: int
    value: date


def extract_date_iso(lines: list[str]) -> str | None:
    cands: list[DateCandidate] = []

    for idx, ln in enumerate(lines):
        u = ln.upper()
        base = 0.0
        if "DATE" in u:
            base += 10.0
        if "INVOICE" in u:
            base += 2.0
        if idx < 5:
            base += 1.0
        base -= idx / 200.0

        for m in _numeric_date_re.finditer(u):
            a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))

            # yyyy-mm-dd
            if a >= 1000:
                dt = _safe_date(a, b, c)
                if dt:
                    cands.append(DateCandidate(base + 0.5, idx, dt))
                continue

            # dd-mm-yyyy or dd-mm-yy (default)
            y = _pivot_year(c)
            dd, mm = a, b
            dt1 = _safe_date(y, mm, dd)
            if dt1:
                cands.append(DateCandidate(base + 0.2, idx, dt1))

            # mm-dd-yyyy alternative (lower priority unless forced)
            if a <= 12 and b <= 12:
                dt2 = _safe_date(y, a, b)
                if dt2:
                    cands.append(DateCandidate(base, idx, dt2))

        for m in _monthname_re.finditer(ln):
            d = int(m.group(1))
            mon = MONTHS[m.group(2).upper()]
            y = _pivot_year(int(m.group(3)))
            dt = _safe_date(y, mon, d)
            if dt:
                cands.append(DateCandidate(base + 0.6, idx, dt))

        for m in _monthname_re2.finditer(ln):
            mon = MONTHS[m.group(1).upper()]
            d = int(m.group(2))
            y = _pivot_year(int(m.group(3)))
            dt = _safe_date(y, mon, d)
            if dt:
                cands.append(DateCandidate(base + 0.4, idx, dt))

    # Prefer modern receipt years if multiple candidates exist
    filtered = [c for c in cands if 1990 <= c.value.year <= 2099]
    if not filtered:
        filtered = cands

    if not filtered:
        return None

    best = max(filtered, key=lambda c: (c.score, -c.idx))
    return best.value.isoformat()


def write_results(rows: list[tuple[str, str | None, str | None]]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "results"

    ws.append(["filename", "date", "total_amount"])
    for fn, dt, amt in rows:
        ws.append([fn, dt, amt])

    # Ensure there is exactly one sheet
    for name in list(wb.sheetnames):
        if name != "results":
            del wb[name]

    wb.save(OUT_XLSX)


def main() -> int:
    files = sorted([p for p in IMG_DIR.iterdir() if p.is_file()])
    rows: list[tuple[str, str | None, str | None]] = []

    for fp in files:
        lines = ocr_text(fp, invert=False, sharpen=True)
        dt = extract_date_iso(lines)
        amt = extract_total_amount(lines)

        if dt is None or amt is None or amt == "0.00":
            soft_lines = ocr_text(fp, invert=False, sharpen=False)
            if dt is None:
                dt = extract_date_iso(soft_lines)
            if amt is None or amt == "0.00":
                soft_amt = extract_total_amount(soft_lines)
                if soft_amt is not None and (amt is None or soft_amt != "0.00"):
                    amt = soft_amt

        if dt is None or amt is None or amt == "0.00":
            inv_lines = ocr_text(fp, invert=True, sharpen=False)
            if dt is None:
                dt = extract_date_iso(inv_lines)
            if amt is None or amt == "0.00":
                inv_amt = extract_total_amount(inv_lines)
                if inv_amt is not None and (amt is None or inv_amt != "0.00"):
                    amt = inv_amt

        rows.append((fp.name, dt, amt))

    write_results(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
