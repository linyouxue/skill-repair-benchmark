"""Extract date and total_amount from receipt images and write to Excel.

Uses multiple OCR passes with voting for robustness.
"""
import os
import re
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps
from openpyxl import Workbook

IMG_DIR = Path("/app/workspace/dataset/img")
OUT_PATH = Path("/app/workspace/stat_ocr.xlsx")

# (keyword, priority) - lower number = higher priority
INCLUSION_KEYWORDS = [
    ("GRAND TOTAL", 1),
    ("GRANDTOTAL", 1),
    ("TOTAL RM", 2),
    ("TOTAL: RM", 2),
    ("TOTAL AMOUNT", 3),
    ("TOTAL DUE", 4),
    ("AMOUNT DUE", 4),
    ("BALANCE DUE", 4),
    ("NETT TOTAL", 4),
    ("NET TOTAL", 4),
    ("TOTAL", 4),
    ("AMOUNT", 4),
]

EXCLUSION_KEYWORDS = [
    "SUBTOTAL",
    "SUB TOTAL",
    "SUB-TOTAL",
    "CASH TENDERED",
    "DISCOUNT",
    "CHANGE",
    "TAX",
    "GST",
    "SST",
]

GST_SUMMARY_MARKERS = ["GST SUMMARY", "TAX SUMMARY", "GST SUNMARY", "GST SUMARY"]


def is_summary_header(line_upper: str) -> bool:
    """Detect a GST/tax summary section header line."""
    if any(mk in line_upper for mk in GST_SUMMARY_MARKERS):
        return True
    # Line containing 'SUMMARY' plus 'AMOUNT' or 'TAX' — generic tax summary header
    if "SUMMARY" in line_upper and ("AMOUNT" in line_upper or "TAX" in line_upper):
        return True
    return False

# number pattern allowing , or . or : as decimal separator (only when exactly 2 digits follow)
AMOUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})+\.\d{2}|\d+[.,:;]\d{2}(?!\d)")


def ocr_variants(image_path: Path) -> list[tuple[str, int]]:
    """Return multiple OCR passes of an image as (text, weight) pairs."""
    img = Image.open(image_path)
    gray = ImageOps.grayscale(img)

    variants_img = [
        ("gray", gray),
        ("autocontrast", ImageOps.autocontrast(gray)),
    ]
    # PSM 4 (single column) suits receipts best. Also use PSM 6 (uniform
    # block) and PSM 11 (sparse text) with equal secondary weight.
    psm_configs = [("--psm 4", 3), ("--psm 6", 2), ("--psm 11", 2)]
    outputs = []
    for _, v in variants_img:
        for psm, weight in psm_configs:
            try:
                outputs.append((pytesseract.image_to_string(v, config=psm), weight))
            except Exception:
                pass
    return outputs


def find_first_inclusion(line_upper: str):
    """Return (position, priority, keyword) for earliest inclusion keyword."""
    best = None
    for kw, prio in INCLUSION_KEYWORDS:
        idx = line_upper.find(kw)
        if idx >= 0:
            if best is None or idx < best[0] or (idx == best[0] and prio < best[1]):
                best = (idx, prio, kw)
    return best


def find_first_exclusion(line_upper: str):
    best = None
    for kw in EXCLUSION_KEYWORDS:
        idx = line_upper.find(kw)
        if idx >= 0:
            if best is None or idx < best[0]:
                best = (idx, kw)
    return best


def normalize_amount(s: str) -> str | None:
    """Normalize OCR-detected number string to a 2-decimal value."""
    s = s.replace(",", "").replace(":", ".").replace(";", ".")
    # If no decimal, invalid
    if "." not in s:
        return None
    # Thousand sep with comma already stripped; "1234.56" OK; "12.345" invalid
    parts = s.split(".")
    if len(parts) != 2:
        return None
    intp, fracp = parts
    if not intp.isdigit() or not fracp.isdigit() or len(fracp) != 2:
        return None
    try:
        f = float(f"{intp}.{fracp}")
    except ValueError:
        return None
    return f"{f:.2f}"


def extract_amount_from_line(line: str) -> str | None:
    """Return the last valid currency amount on the line."""
    matches = AMOUNT_RE.findall(line)
    for m in reversed(matches):
        # for comma-thousands-sep match, keep commas; normalize_amount handles.
        norm = normalize_amount(m)
        if norm is not None:
            return norm
    return None


def extract_total(text: str) -> str | None:
    lines = text.splitlines()
    candidates = []  # (priority, line_index, amount)
    past_gst_summary = False
    for i, line in enumerate(lines):
        upper = line.upper()
        if is_summary_header(upper):
            past_gst_summary = True
            continue
        if past_gst_summary:
            continue
        inc = find_first_inclusion(upper)
        if not inc:
            continue
        inc_pos, prio, kw = inc
        exc = find_first_exclusion(upper)
        if exc and exc[0] < inc_pos:
            continue
        amt = extract_amount_from_line(line)
        if amt is None:
            # Fallback: scan next non-empty line for the last decimal number,
            # but skip lines that look like separate labels (exclusion kws
            # or 'CASH'/'MYR'/'RM' alone, etc.) to avoid grabbing a nearby
            # payment amount.
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                next_upper = lines[j].upper()
                if not any(ek in next_upper for ek in EXCLUSION_KEYWORDS) \
                        and "CASH" not in next_upper \
                        and "PAYMENT" not in next_upper \
                        and "VISA" not in next_upper \
                        and "MASTERCARD" not in next_upper:
                    amt = extract_amount_from_line(lines[j])
        if amt is None:
            continue
        candidates.append((prio, i, amt))
    if not candidates:
        return None
    best_prio = min(c[0] for c in candidates)
    filtered = [c for c in candidates if c[0] == best_prio]
    filtered.sort(key=lambda c: c[1])
    return filtered[-1][2]


DATE_PATTERNS = [
    (re.compile(r"(?<!\d)(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?!\d)"), "dmy4"),
    (re.compile(r"(?<!\d)(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})[-/](\d{1,2})[-/](\d{2})(?!\d)"), "dmy2"),
]


def extract_date(text: str) -> str | None:
    for line in text.splitlines():
        for pat, fmt in DATE_PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            try:
                if fmt == "dmy4":
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif fmt == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    d, mo, y = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
                if 1 <= d <= 31 and 1 <= mo <= 12 and 1990 <= y <= 2099:
                    return f"{y:04d}-{mo:02d}-{d:02d}"
            except ValueError:
                continue
    return None


def vote_weighted(items: list[tuple[object, int]]) -> object:
    """Return the value with highest total weight; None if all values are None."""
    scores: dict = {}
    first_seen: dict = {}
    for i, (val, w) in enumerate(items):
        if val is None:
            continue
        scores[val] = scores.get(val, 0) + w
        if val not in first_seen:
            first_seen[val] = i
    if not scores:
        return None
    max_score = max(scores.values())
    best = [v for v, s in scores.items() if s == max_score]
    best.sort(key=lambda v: first_seen[v])
    return best[0]


def process_image(image_path: Path):
    variants = ocr_variants(image_path)
    totals = [(extract_total(t), w) for t, w in variants]
    dates = [(extract_date(t), w) for t, w in variants]
    return vote_weighted(dates), vote_weighted(totals)


def main():
    rows = []
    files = sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    for fn in files:
        print(f"Processing {fn}", flush=True)
        date, total = process_image(IMG_DIR / fn)
        print(f"  date={date} total={total}", flush=True)
        rows.append((fn, date, total))

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for fn, date, total in rows:
        ws.append([fn, date, total])
    wb.save(OUT_PATH)
    print(f"Saved {OUT_PATH}")


if __name__ == "__main__":
    main()
