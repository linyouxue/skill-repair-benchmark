import os
import re
import sys
from pathlib import Path
import pytesseract
from PIL import Image, ImageOps, ImageFilter
from openpyxl import Workbook

IMG_DIR = Path("/app/workspace/dataset/img")
OUT_XLSX = Path("/app/workspace/stat_ocr.xlsx")

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

MONEY_STRICT = re.compile(r'(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})(?![\d.])')

PRIMARY_KEYWORDS = [
    ("GRAND TOTAL", 100, True),
    ("TOTAL RM", 90, True),
    ("TOTAL: RM", 90, True),
    ("TOTAL AMOUNT", 80, True),
    ("TOTAL DUE", 70, True),
    ("AMOUNT DUE", 70, True),
    ("BALANCE DUE", 70, True),
    ("NETT TOTAL", 70, True),
    ("NET TOTAL", 70, True),
    ("TOTAL", 60, False),
    ("AMOUNT", 60, False),
]

ABSOLUTE_EXCLUSION = ["SUBTOTAL", "SUB TOTAL", "SUB-TOTAL", "DISCOUNT", "CASH TENDERED"]
TAX_EXCLUSION = ["GST", "TAX", "SST"]
EXCL_RE = re.compile(r'\bEXCL', re.IGNORECASE)
CHANGE_RE = re.compile(r'\bCHANGE\b', re.IGNORECASE)
TAX_SUM_RE = re.compile(r'\bTOTAL\s+(GST|TAX|SST)\b', re.IGNORECASE)
TAX_PAYABLE_RE = re.compile(r'\b(GST|TAX|SST)\s*(PAYABLE|AMOUNT|AMT|ONLY)\b', re.IGNORECASE)
LINE_STARTS_TAX_RE = re.compile(r'^\s*[^A-Za-z0-9]*\s*(GST|TAX|SST)\b', re.IGNORECASE)


def _repair_line(s):
    """OCR repairs for monetary values:
      '85. 54'  -> '85.54' (stray space after decimal)
      '92:80'   -> '92.80' (colon mis-read as decimal)
      '17,76'   -> '17.76' (comma used as decimal when only 2 digits follow)
    """
    r = re.sub(r'(\d)\.\s+(\d{2})(?!\d)', r'\1.\2', s)
    r = re.sub(r'(\d)[:;](\d{2})(?!\d)', r'\1.\2', r)
    r = re.sub(r'(?<=\d),(\d{2})(?!\d)', r'.\1', r)
    return r


def extract_last_money(line):
    """Extract last monetary value from a line (with OCR repairs)."""
    repaired = _repair_line(line)
    matches = list(MONEY_STRICT.finditer(repaired))
    if matches:
        m = matches[-1]
        return m.group(1).replace(',', '') + '.' + m.group(2)
    # Try space-as-decimal: '92 80' -> '92.80'
    r2 = re.sub(r'(\d)\s+(\d{2})(?!\d)', r'\1.\2', repaired)
    matches = list(MONEY_STRICT.finditer(r2))
    if matches:
        m = matches[-1]
        return m.group(1).replace(',', '') + '.' + m.group(2)
    return None


def line_has_exclusion(line, primary_keyword):
    """Decide whether a candidate line should be skipped.

    GRAND TOTAL overrides all exclusions. Otherwise:
      - Hard exclusions: SUBTOTAL, DISCOUNT, CASH TENDERED, CHANGE.
      - Tax lines that are NOT totals get skipped:
          * "TOTAL GST/TAX/SST" (sum of tax)
          * lines where the tax keyword starts the line ("GST Summary ...")
          * "GST/TAX PAYABLE/AMOUNT/ONLY" patterns
          * "Total EXCL... GST" (total excluding tax == a subtotal)
      - Otherwise the line is kept, even if it mentions GST (e.g.
        "Total Sales Incl GST", "Total Rounded").
    """
    upper = line.upper()
    if primary_keyword == "GRAND TOTAL":
        return False
    for ex in ABSOLUTE_EXCLUSION:
        if ex in upper:
            return True
    if CHANGE_RE.search(upper):
        return True
    if TAX_SUM_RE.search(upper):
        return True
    has_tax = any(ex in upper for ex in TAX_EXCLUSION)
    if has_tax:
        if EXCL_RE.search(upper):
            return True
        if TAX_PAYABLE_RE.search(upper):
            return True
        if LINE_STARTS_TAX_RE.search(line):
            return True
    return False


def find_total(text):
    """Find the total amount using tiered keyword priority.

    Steps:
      1. Scan each line for primary keywords (highest priority first).
      2. Apply exclusion rules per keyword.
      3. Collect candidates with (priority, is_direct, line_index, value).
      4. Keep only the highest-priority tier.
      5. Within that tier, choose the most frequent value; break ties by
         preferring direct same-line matches, then the latest line position.
    """
    lines = text.split('\n')
    candidates = []
    # Everything below a "GST Summary" / "TAX Summary" header is a tax breakdown
    summary_start = len(lines)
    for i, line in enumerate(lines):
        up = line.upper()
        if re.search(r'\b(GST|TAX|SST)\s+SUMMARY\b', up):
            summary_start = i
            break

    for i, line in enumerate(lines):
        if i >= summary_start:
            break
        upper = line.upper()
        for kw, prio, allow_fallback in PRIMARY_KEYWORDS:
            if kw in upper:
                if line_has_exclusion(line, kw):
                    break
                val = extract_last_money(line)
                is_direct = val is not None
                if val is None and allow_fallback:
                    for j in range(i + 1, min(i + 4, len(lines))):
                        nxt = lines[j].strip()
                        if not nxt:
                            continue
                        val = extract_last_money(nxt)
                        break
                if val:
                    candidates.append((prio, is_direct, i, val))
                break

    if not candidates:
        return None

    top_prio = max(c[0] for c in candidates)
    top = [c for c in candidates if c[0] == top_prio]

    # Tally values; prefer most frequent, then direct, then latest line
    counts = {}
    for prio, is_direct, idx, val in top:
        info = counts.setdefault(val, {"count": 0, "direct": False, "last_idx": -1})
        info["count"] += 1
        info["direct"] = info["direct"] or is_direct
        info["last_idx"] = max(info["last_idx"], idx)

    best = max(counts.items(), key=lambda kv: (kv[1]["count"], 1 if kv[1]["direct"] else 0, kv[1]["last_idx"]))
    return best[0]


DATE_PATTERNS = [
    # dd/mm/yyyy or dd-mm-yyyy
    (re.compile(r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b'), 'dmy'),
    # yyyy/mm/dd
    (re.compile(r'\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b'), 'ymd'),
    # dd MMM yyyy
    (re.compile(r'\b(\d{1,2})[\s\-]+([A-Za-z]{3,9})[\s\-,]+(\d{2,4})\b'), 'dMy'),
    # MMM dd, yyyy
    (re.compile(r'\b([A-Za-z]{3,9})[\s\-]+(\d{1,2})[\s\-,]+(\d{2,4})\b'), 'Mdy'),
]


def normalize_year(y):
    y = int(y)
    if y < 100:
        y = 2000 + y if y < 70 else 1900 + y
    return y


def valid_date(y, m, d):
    if not (1 <= m <= 12):
        return False
    if not (1 <= d <= 31):
        return False
    if not (2000 <= y <= 2099):
        return False
    return True


def find_date(text):
    for line in text.split('\n'):
        for pat, kind in DATE_PATTERNS:
            for m in pat.finditer(line):
                try:
                    if kind == 'dmy':
                        d, mo, y = int(m.group(1)), int(m.group(2)), normalize_year(m.group(3))
                    elif kind == 'ymd':
                        y, mo, d = normalize_year(m.group(1)), int(m.group(2)), int(m.group(3))
                    elif kind == 'dMy':
                        mon_str = m.group(2).lower()
                        if mon_str not in MONTHS:
                            continue
                        d, mo, y = int(m.group(1)), MONTHS[mon_str], normalize_year(m.group(3))
                    elif kind == 'Mdy':
                        mon_str = m.group(1).lower()
                        if mon_str not in MONTHS:
                            continue
                        mo, d, y = MONTHS[mon_str], int(m.group(2)), normalize_year(m.group(3))
                    if valid_date(y, mo, d):
                        return f"{y:04d}-{mo:02d}-{d:02d}"
                except Exception:
                    continue
    return None


def ocr_variants(img_path):
    img = Image.open(img_path)
    gray = ImageOps.grayscale(img)
    w, h = img.size
    variants = [
        ("gray_auto", ImageOps.autocontrast(gray)),
        ("sharp", gray.filter(ImageFilter.SHARPEN)),
        ("up3x", ImageOps.autocontrast(img.resize((w * 3, h * 3), Image.LANCZOS).convert('L'))),
    ]
    psm_modes = ['--psm 6', '--psm 4', '--psm 11']
    texts = []
    for name, v in variants:
        for psm in psm_modes:
            try:
                t = pytesseract.image_to_string(v, config=psm)
                if t.strip():
                    texts.append(t)
            except Exception:
                pass
    return texts


def vote(values):
    """Return majority value, or first if tie."""
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
    best = max(order, key=lambda x: (counts[x], -order.index(x)))
    return best


def process_image(img_path):
    texts = ocr_variants(img_path)
    dates = []
    totals = []
    for t in texts:
        d = find_date(t)
        tot = find_total(t)
        dates.append(d)
        totals.append(tot)
    date = vote(dates)
    total = vote(totals)
    return date, total


def main():
    files = sorted([f for f in os.listdir(IMG_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    rows = []
    for fname in files:
        print(f"Processing {fname}...", flush=True)
        try:
            date, total = process_image(IMG_DIR / fname)
        except Exception as e:
            print(f"  ERROR: {e}")
            date, total = None, None
        print(f"  date={date} total={total}")
        rows.append((fname, date, total))

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for fname, date, total in rows:
        ws.append([fname, date, total])
    wb.save(OUT_XLSX)
    print(f"Wrote {OUT_XLSX}")


if __name__ == "__main__":
    main()
