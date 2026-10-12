import os
import re
from collections import Counter

import pytesseract
from PIL import Image, ImageOps, ImageFilter
from openpyxl import Workbook

IMG_DIR = "/app/workspace/dataset/img"
OUT_XLSX = "/app/workspace/stat_ocr.xlsx"

PRIORITY_TIERS = [
    [r"GRAND\s+TOTAL"],
    [r"TOTAL\s*[:\s]\s*R[MN]", r"TOTAL\s*\(\s*R[MN]\s*\)"],
    [r"TOTAL\s+AMOUNT"],
    [r"NETT?\s+TOTAL", r"TOTAL\s+DUE", r"AMOUNT\s+DUE", r"BALANCE\s+DUE", r"TOTAL", r"AMOUNT"],
]
EXCLUSION = [
    r"SUB[\s-]?TOTAL",
    r"\bTAX\b",
    r"\bGST\b",
    r"\bSST\b",
    r"DISCOUNT",
    r"CHANGE",
    r"CASH\s+TENDERED",
    r"\bCASH\b",
    r"ROUNDING\s+ADJ",
    r"\bITEM\b",
    r"\bTEM\b",
    r"PAYMENT",
    r"VISA",
    r"MASTERCARD",
    r"DESCRIPTION",
    r"\bQTY\b",
    r"QUANTITY",
    r"U\.?\s*PRICE",
    r"UNIT\s+PRICE",
    r"\bPRICE\b",
    r"SALES\s*TAX",
    r"RELIEF",
    r"EXCL",
    r"EXCLUDED",
]
SECTION_CUTOFF = re.compile(r"(GST|TAX)\s+SUMMARY", re.IGNORECASE)

AMOUNT_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+(?:\.\d{2})|\d+\.\d{2})(?![\d])")


def line_leftmost(line, patterns):
    best = None
    for p in patterns:
        m = re.search(p, line, re.IGNORECASE)
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


def extract_amounts(line):
    return [m.group(1) for m in AMOUNT_RE.finditer(line)]


def normalize(s):
    s = s.replace(",", "")
    try:
        return f"{float(s):.2f}"
    except ValueError:
        return None


def find_total_tiered(text):
    """Return (tier_idx, value) or None."""
    raw_lines = text.splitlines()
    lines = []
    for l in raw_lines:
        if SECTION_CUTOFF.search(l):
            break
        if l.strip():
            lines.append(l)
    for tier_idx, tier in enumerate(PRIORITY_TIERS):
        candidate = None
        for i, line in enumerate(lines):
            pos = line_leftmost(line, tier)
            if pos is None:
                continue
            excl = line_leftmost(line, EXCLUSION)
            if excl is not None and excl < pos:
                continue
            amounts = extract_amounts(line)
            val = None
            if amounts:
                val = amounts[-1]
            elif i + 1 < len(lines):
                next_line = lines[i + 1]
                next_excl = line_leftmost(next_line, EXCLUSION)
                next_prio = line_leftmost(next_line, [p for tier in PRIORITY_TIERS for p in tier])
                if next_excl is None and next_prio is None:
                    next_amounts = extract_amounts(next_line)
                    if next_amounts:
                        val = next_amounts[-1]
            if val is not None:
                candidate = (tier_idx, normalize(val))
        if candidate is not None:
            return candidate
    return None


DATE_PATTERNS = [
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b"), "dmy4"),
    (re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})\b"), "dmy2"),
]


def find_date(text):
    for pat, kind in DATE_PATTERNS:
        for m in pat.finditer(text):
            g1, g2, g3 = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if kind == "ymd":
                y, mo, d = g1, g2, g3
            elif kind == "dmy4":
                d, mo, y = g1, g2, g3
            else:
                d, mo, y = g1, g2, 2000 + g3
            if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2099:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def ocr_variants(path):
    img = Image.open(path)
    g = ImageOps.grayscale(img)
    auto = ImageOps.autocontrast(g)
    sharp = g.filter(ImageFilter.SHARPEN)
    variants = [auto, sharp, g]
    configs = ["--psm 6", "--psm 4", "--psm 3"]
    texts = []
    for v in variants:
        for cfg in configs:
            try:
                texts.append(pytesseract.image_to_string(v, config=cfg))
            except Exception:
                pass
    return texts


def process(path):
    texts = ocr_variants(path)

    # Date: majority vote across passes
    date_votes = Counter()
    for t in texts:
        d = find_date(t)
        if d:
            date_votes[d] += 1
    date = date_votes.most_common(1)[0][0] if date_votes else None

    # Total: find best tier across all passes, then majority vote
    best_tier = None
    tier_values = {}  # tier -> Counter of values
    for t in texts:
        r = find_total_tiered(t)
        if r is None:
            continue
        tier, val = r
        if val is None:
            continue
        if best_tier is None or tier < best_tier:
            best_tier = tier
        tier_values.setdefault(tier, Counter())[val] += 1

    total = None
    if best_tier is not None:
        total = tier_values[best_tier].most_common(1)[0][0]

    return date, total


def main():
    files = sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith(".jpg"))
    results = []
    for fname in files:
        path = os.path.join(IMG_DIR, fname)
        date, total = process(path)
        print(f"{fname}: date={date} total={total}")
        results.append((fname, date, total))

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for fname, date, total in results:
        ws.append([fname, date, total])
    wb.save(OUT_XLSX)


if __name__ == "__main__":
    main()
