import os
import re
import json
from pathlib import Path
from decimal import Decimal

import pytesseract
from PIL import Image, ImageOps, ImageFilter
from openpyxl import Workbook

IMG_DIR = Path("/app/workspace/dataset/img")
OUT_XLSX = Path("/app/workspace/stat_ocr.xlsx")

PRIORITY_GROUPS = [
    ("GRAND TOTAL",),
    ("TOTAL RM", "TOTAL: RM"),
    ("TOTAL AMOUNT",),
    ("TOTAL", "AMOUNT", "TOTAL DUE", "AMOUNT DUE", "BALANCE DUE", "NETT TOTAL", "NET TOTAL"),
]

EXCLUSION_KEYWORDS = [
    "SUBTOTAL", "SUB TOTAL", "TAX", "GST", "SST",
    "DISCOUNT", "CHANGE", "CASH TENDERED",
]

# Allow lines like "Total (Incl. GST)" to pass despite GST keyword.
INCL_PATTERN = re.compile(r"\binc(?:l|luding|lusive)\.?\b", re.IGNORECASE)

MONEY_STRICT = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?![\d])")
MONEY_COMMA = re.compile(r"(?<![\d.,])\d+,\d{2}(?![\d])")
MONEY_SPACE = re.compile(r"(?<![\d.,])\d+\s\d{2}(?![\d.,\d])")


def ocr_variants(path: Path):
    """Return several OCR variants of the same image for voting."""
    img = Image.open(path)
    w, h = img.size
    gray = ImageOps.grayscale(img)
    auto = ImageOps.autocontrast(gray)
    big = img.resize((w * 3, h * 3), Image.LANCZOS).convert("L")
    big = ImageOps.autocontrast(big)
    big2 = img.resize((w * 2, h * 2), Image.LANCZOS).convert("L")
    big2 = ImageOps.autocontrast(big2)
    variants = [
        ("auto|psm3", pytesseract.image_to_string(auto, config="--psm 3")),
        ("auto|psm6", pytesseract.image_to_string(auto, config="--psm 6")),
        ("auto|psm4", pytesseract.image_to_string(auto, config="--psm 4")),
        ("3x|psm6", pytesseract.image_to_string(big, config="--psm 6")),
        ("3x|psm4", pytesseract.image_to_string(big, config="--psm 4")),
        ("2x|psm6", pytesseract.image_to_string(big2, config="--psm 6")),
    ]
    return variants


# ------------------- date extraction -------------------

DATE_PATTERNS = [
    # DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b"), "dmy4"),
    # YYYY-MM-DD, YYYY/MM/DD
    (re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b"), "ymd4"),
    # DD-MM-YY, DD/MM/YY
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})\b"), "dmy2"),
    # DDMMYYYY compact (no separators) - e.g. 2032018 (missing leading zero), 20032018
    (re.compile(r"\bDate\s*[:.]?\s*(\d{1,2})\s*[-/.\s]?\s*(\d{1,2})\s*[-/.\s]?\s*(\d{4})\b", re.IGNORECASE), "dmy4_loose"),
]


def valid_date(d, m, y):
    try:
        d = int(d); m = int(m); y = int(y)
    except Exception:
        return None
    if y < 100:
        y += 2000
    if not (1 <= m <= 12 and 1 <= d <= 31 and 2000 <= y <= 2099):
        return None
    # month-days check
    mdays = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if d > mdays[m - 1]:
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


def extract_date(text: str):
    for pat, kind in DATE_PATTERNS:
        for m in pat.finditer(text):
            a, b, c = m.group(1), m.group(2), m.group(3)
            if kind == "ymd4":
                iso = valid_date(c, b, a)
            else:
                iso = valid_date(a, b, c)
            if iso:
                return iso
    return None


def extract_date_multi(variants):
    """Vote across OCR variants; prefer most-common valid ISO date."""
    from collections import Counter

    dates = []
    for _, txt in variants:
        iso = extract_date(txt)
        if iso:
            dates.append(iso)
    if not dates:
        return None
    counts = Counter(dates)
    top = max(counts.values())
    for d in dates:
        if counts[d] == top:
            return d
    return dates[0]


# ------------------- total extraction -------------------


def line_excluded(line_upper: str) -> bool:
    # Allow qualifier phrases like "Incl GST", "Including GST", "Incl. of GST"
    if INCL_PATTERN.search(line_upper):
        # Only tax-related exclusions are suppressed by Incl pattern
        tax_free = re.sub(r"\b(GST|SST|TAX)\b", "", line_upper)
        for kw in ("SUBTOTAL", "SUB TOTAL", "DISCOUNT", "CHANGE", "CASH TENDERED"):
            if kw in tax_free:
                return True
        return False
    for kw in EXCLUSION_KEYWORDS:
        if kw in line_upper:
            return True
    return False


def parse_money_from_line(line: str):
    """Return list of Decimal candidates found on a line (in order)."""
    cands = []
    for m in MONEY_STRICT.finditer(line):
        s = m.group(0).replace(",", "")
        try:
            cands.append(Decimal(s))
        except Exception:
            pass
    if cands:
        return cands
    # Fallback: comma-as-decimal
    for m in MONEY_COMMA.finditer(line):
        s = m.group(0).replace(",", ".")
        try:
            cands.append(Decimal(s))
        except Exception:
            pass
    if cands:
        return cands
    # Fallback: space-as-decimal "538 00"
    for m in MONEY_SPACE.finditer(line):
        s = m.group(0).replace(" ", ".")
        try:
            cands.append(Decimal(s))
        except Exception:
            pass
    return cands


GST_SUMMARY_RE = re.compile(r"\b(GST|TAX)\s+SUMMARY\b", re.IGNORECASE)


def _in_tax_summary(upper_lines, i):
    """True if line i is at or after a 'GST SUMMARY' / 'TAX SUMMARY' header."""
    for j in range(i, -1, -1):
        if GST_SUMMARY_RE.search(upper_lines[j]):
            return True
    return False


DIGIT_RE = re.compile(r"\d")


def extract_total_from_text(text: str):
    """Return (priority_index, chosen_amount, all_candidates_in_order) or None.

    priority_index is 0-based: lower = higher priority.
    chosen_amount is the last candidate seen in that priority group.
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    upper = [ln.upper() for ln in lines]

    for gi, group in enumerate(PRIORITY_GROUPS):
        all_cands = []
        for i, lu in enumerate(upper):
            match_kw = None
            for kw in group:
                if kw in lu:
                    match_kw = kw
                    break
            if not match_kw:
                continue
            if line_excluded(lu):
                continue
            if _in_tax_summary(upper, i):
                continue
            cands = parse_money_from_line(lines[i])
            if cands:
                all_cands.append(cands[-1])
                continue
            # Fallback to next line only when the current line has no digits.
            if DIGIT_RE.search(lines[i]):
                continue
            if i + 1 < len(lines):
                next_u = upper[i + 1]
                if not line_excluded(next_u):
                    nc = parse_money_from_line(lines[i + 1])
                    if nc:
                        all_cands.append(nc[-1])
        if all_cands:
            return (gi, all_cands[-1], all_cands)
    return None


def extract_total_multi(variants):
    """Vote across OCR variants, preferring higher priority group.

    Within the best priority group, simple majority vote on each variant's
    chosen "last" value. Ties are broken by preferring the smaller candidate
    when values are within 0.05 (indicating a rounding adjustment); otherwise
    by first-seen variant order.
    """
    from collections import defaultdict

    by_prio = defaultdict(list)  # prio -> list of (chosen, order_idx)
    for order_idx, (_, txt) in enumerate(variants):
        res = extract_total_from_text(txt)
        if res is None:
            continue
        prio, chosen, _ = res
        by_prio[prio].append((chosen, order_idx))

    if not by_prio:
        return None
    best_prio = min(by_prio.keys())
    entries = by_prio[best_prio]

    counts = defaultdict(int)
    first_seen = {}
    for chosen, order_idx in entries:
        counts[chosen] += 1
        first_seen.setdefault(chosen, order_idx)

    top_count = max(counts.values())
    winners = [v for v, c in counts.items() if c == top_count]
    if len(winners) == 1:
        return winners[0]
    # Tie-break: if two tied values are within 0.05 (rounding), prefer smaller.
    winners.sort(key=lambda v: first_seen[v])
    a, b = winners[0], winners[1]
    if abs(a - b) <= Decimal("0.05"):
        return min(winners)
    return winners[0]


def fmt_amount(d):
    if d is None:
        return None
    return f"{d:.2f}"


def main():
    files = sorted(p for p in IMG_DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    rows = []
    for p in files:
        variants = ocr_variants(p)
        date = extract_date_multi(variants)
        total = extract_total_multi(variants)
        rows.append((p.name, date, fmt_amount(total)))
        print(f"{p.name}  date={date}  total={fmt_amount(total)}")

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for r in rows:
        ws.append(list(r))
    wb.save(OUT_XLSX)
    print(f"wrote {OUT_XLSX}")


if __name__ == "__main__":
    main()
