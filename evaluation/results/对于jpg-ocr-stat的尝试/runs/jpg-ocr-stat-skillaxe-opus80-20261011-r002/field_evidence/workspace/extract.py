"""Extract date and total amount from receipt images, write to xlsx."""
import os
import re
from pathlib import Path

import pytesseract
from PIL import Image, ImageFilter, ImageOps
from openpyxl import Workbook

IMG_DIR = Path("/app/workspace/dataset/img")
OUT_XLSX = Path("/app/workspace/stat_ocr.xlsx")

PRIMARY_KEYWORDS = [
    ["GRAND TOTAL", "GRANDTOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    ["TOTAL", "AMOUNT", "TOTAL DUE", "AMOUNT DUE",
     "BALANCE DUE", "NETT TOTAL", "NET TOTAL"],
]

# Hard exclusions: lines about subtotals, discount, change, cash tendered,
# or that are pure tax summary rows (handled separately for GST/SST/TAX
# because those often appear as "Incl GST" qualifier on the real total line).
HARD_EXCLUSIONS = [
    "SUBTOTAL", "SUB TOTAL", "SUB-TOTAL",
    "DISCOUNT", "CHANGE", "CASH TENDERED",
]
TAX_KEYWORDS = ["TAX", "GST", "SST"]
# Match INCL / INCLUSIVE / INCLUDING / INCLUDES tolerant of OCR errors
# that corrupt the leading "I" (e.g. "[NCL", "|NCL", "TNCL"). Testing for
# the "NCL" trigraph covers all these variants and is highly distinctive.
INCL_RE = re.compile(r"NCL")

MONEY_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})")

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def ocr_variants(path: Path):
    """Run OCR with several preprocessing + PSM combos; return list of texts."""
    img = Image.open(path)
    gray = ImageOps.grayscale(img)
    w, h = img.size
    variants = [
        img,
        ImageOps.autocontrast(gray),
        gray.filter(ImageFilter.SHARPEN),
        ImageOps.autocontrast(img.resize((w * 2, h * 2), Image.LANCZOS).convert("L")),
    ]
    psm_modes = ["--psm 6", "--psm 4", "--psm 11"]
    outputs = []
    for v in variants:
        for psm in psm_modes:
            try:
                outputs.append(pytesseract.image_to_string(v, config=psm))
            except Exception:
                pass
    return outputs


def normalize_amount(num_text: str):
    """Parse monetary token; return float or None."""
    s = num_text.strip().replace(" ", "").replace("O", "0").replace("o", "0")
    m = MONEY_RE.search(s)
    if m:
        return float(m.group(1).replace(",", "") + "." + m.group(2))
    return None


def find_amount_on_line(line: str):
    """Return last money value on line, or None."""
    matches = list(MONEY_RE.finditer(line))
    if not matches:
        return None
    m = matches[-1]
    return float(m.group(1).replace(",", "") + "." + m.group(2))


def _normalize_for_keywords(up_line: str) -> str:
    """Repair common OCR substitutions so keyword checks are more robust."""
    return (up_line.replace("[", "I").replace("|", "I")
                   .replace("]", "L").replace("1NCL", "INCL"))


def is_excluded(up_line: str, tier_is_grand: bool) -> bool:
    """Check whether a line should be excluded as subtotal/tax/etc."""
    if tier_is_grand:
        # GRAND TOTAL dominates all exclusions.
        return False
    if any(ex in up_line for ex in HARD_EXCLUSIONS):
        return True
    if any(tk in up_line for tk in TAX_KEYWORDS):
        # Keep if the tax keyword is modified by an "Incl"-style marker,
        # meaning the amount is the tax-inclusive total (e.g. "Incl GST").
        if not INCL_RE.search(up_line):
            return True
    return False


def _cutoff_index(upper_lines):
    """Index of the first CASH/CHANGE line (section after is a summary)."""
    for i, up in enumerate(upper_lines):
        if re.search(r"\bCASH\b", up) or re.search(r"\bCHANGE\b", up):
            return i
    return len(upper_lines)


def extract_total(text: str):
    """Apply priority keyword rules to extract total from OCR text."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    upper_lines = [_normalize_for_keywords(ln.upper()) for ln in lines]
    cutoff = _cutoff_index(upper_lines)

    for tier in PRIMARY_KEYWORDS:
        tier_is_grand = tier is PRIMARY_KEYWORDS[0]
        # Pass 1: lines with keyword + amount on same line (prefer last
        # match before CASH/CHANGE; fall back to last overall).
        best_before = None
        best_after = None
        split_fallback = None  # keyword line with no amount, next line has one
        for idx, up in enumerate(upper_lines):
            if not any(kw in up for kw in tier):
                continue
            if is_excluded(up, tier_is_grand):
                continue
            val = find_amount_on_line(lines[idx])
            if val is not None:
                if idx < cutoff:
                    best_before = val
                else:
                    best_after = val
            else:
                # Try next non-blank lines for a split amount.
                for j in range(idx + 1, min(idx + 3, len(lines))):
                    nxt_up = upper_lines[j]
                    if is_excluded(nxt_up, tier_is_grand):
                        continue
                    v2 = find_amount_on_line(lines[j])
                    if v2 is not None:
                        split_fallback = v2
                        break
        if best_before is not None:
            return best_before
        if best_after is not None:
            return best_after
        if split_fallback is not None:
            return split_fallback
    return None


DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    (re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b"), "dmy"),
    # DD/MM/YY
    (re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})\b"), "dmy2"),
    # YYYY/MM/DD
    (re.compile(r"\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b"), "ymd"),
    # DD Mon YYYY
    (re.compile(r"\b(\d{1,2})[\s\-]+([A-Za-z]{3,9})[\s\-]+(\d{2,4})\b"), "dmony"),
]


def parse_date(text: str):
    """Return ISO date string if found, else None."""
    for pat, kind in DATE_PATTERNS:
        for m in pat.finditer(text):
            try:
                if kind == "dmy":
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif kind == "dmy2":
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    y += 2000 if y < 70 else 1900
                elif kind == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif kind == "dmony":
                    d = int(m.group(1))
                    mon_key = m.group(2).upper()[:4]
                    if mon_key not in MONTHS:
                        mon_key = m.group(2).upper()[:3]
                    if mon_key not in MONTHS:
                        continue
                    mo = MONTHS[mon_key]
                    y = int(m.group(3))
                    if y < 100:
                        y += 2000 if y < 70 else 1900
                if 1 <= mo <= 12 and 1 <= d <= 31 and 1990 <= y <= 2099:
                    return f"{y:04d}-{mo:02d}-{d:02d}"
            except Exception:
                continue
    return None


def vote(values):
    """Return the most common non-None value; break ties by first occurrence."""
    counts = {}
    order = []
    for v in values:
        if v is None:
            continue
        if v not in counts:
            counts[v] = 0
            order.append(v)
        counts[v] += 1
    if not counts:
        return None
    best = max(order, key=lambda k: (counts[k], -order.index(k)))
    return best


def process_image(path: Path):
    texts = ocr_variants(path)
    dates = [parse_date(t) for t in texts]
    totals = [extract_total(t) for t in texts]
    date = vote(dates)
    total = vote(totals)
    total_str = f"{total:.2f}" if total is not None else None
    return date, total_str


def main():
    files = sorted(p for p in IMG_DIR.iterdir()
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for p in files:
        date, total = process_image(p)
        print(f"{p.name}: date={date}, total={total}")
        ws.append([p.name, date, total])
    wb.save(OUT_XLSX)
    print(f"Wrote {OUT_XLSX}")


if __name__ == "__main__":
    main()
