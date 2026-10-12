import os
import re
import json
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from openpyxl import Workbook

IMG_DIR = "/app/workspace/dataset/img"
OUT_XLSX = "/app/workspace/stat_ocr.xlsx"

MONEY_STRICT = re.compile(r'(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})(?![\d.])')


def parse_money(token: str):
    if token is None:
        return None
    s = token.strip().replace('"', '').replace('~', '').replace('—', '')
    m = MONEY_STRICT.search(s)
    if m:
        return float(m.group(1).replace(',', '') + '.' + m.group(2))
    s2 = re.sub(r'(\d)[:;](\d{2})\b', r'\1.\2', s)
    m = MONEY_STRICT.search(s2)
    if m:
        return float(m.group(1).replace(',', '') + '.' + m.group(2))
    s3 = re.sub(r'(\d)\s+(\d{2})\b', r'\1.\2', s)
    m = MONEY_STRICT.search(s3)
    if m:
        return float(m.group(1).replace(',', '') + '.' + m.group(2))
    return None


def extract_amount_from_line(line: str):
    """Extract last money-looking amount from a line."""
    # Find all strict money matches, return the last one.
    matches = list(MONEY_STRICT.finditer(line))
    if matches:
        m = matches[-1]
        return float(m.group(1).replace(',', '') + '.' + m.group(2))
    # Try repairs on whole line
    return parse_money(line)


EXCLUSION_KEYWORDS = [
    "SUBTOTAL", "SUB TOTAL", "TAX", "GST", "SST",
    "DISCOUNT", "CHANGE", "CASH TENDERED",
]

PRIORITY_KEYWORDS = [
    ["GRAND TOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    ["TOTAL", "AMOUNT", "TOTAL DUE", "AMOUNT DUE", "BALANCE DUE", "NETT TOTAL", "NET TOTAL"],
]


def line_excluded(upper_line: str, primary_keyword: str) -> bool:
    """A line is excluded if it contains an exclusion keyword, UNLESS the matched
    primary keyword itself is 'more specific' and present (e.g. GRAND TOTAL takes
    precedence over SUBTOTAL/TAX)."""
    # If the primary keyword is GRAND TOTAL, it takes precedence.
    if primary_keyword == "GRAND TOTAL":
        return False
    for ex in EXCLUSION_KEYWORDS:
        if ex in upper_line:
            return True
    return False


def find_total(text: str):
    lines = [l.rstrip() for l in text.splitlines()]
    for tier_idx, tier in enumerate(PRIORITY_KEYWORDS):
        # Pass 1: collect same-line (keyword + amount) matches.
        same_line_matches = []
        for i, line in enumerate(lines):
            upper = line.upper()
            matched_kw = next((kw for kw in tier if kw in upper), None)
            if matched_kw is None:
                continue
            if line_excluded(upper, matched_kw):
                continue
            amt = extract_amount_from_line(line)
            if amt is not None:
                same_line_matches.append(amt)
        if same_line_matches:
            # For the generic TOTAL tier (last), prefer the LAST match (bottom of
            # receipt), as earlier "Total" lines may be subtotals/breakdowns whose
            # exclusion keywords were corrupted by OCR.
            if tier_idx == len(PRIORITY_KEYWORDS) - 1:
                return same_line_matches[-1]
            return same_line_matches[0]
        # Pass 2: fallback to next non-blank line for keyword-only lines.
        for i, line in enumerate(lines):
            upper = line.upper()
            matched_kw = next((kw for kw in tier if kw in upper), None)
            if matched_kw is None:
                continue
            if line_excluded(upper, matched_kw):
                continue
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j].strip()
                if not nxt:
                    continue
                amt = extract_amount_from_line(nxt)
                if amt is not None:
                    return amt
                break
    return None


DATE_PATTERNS = [
    # DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
    (re.compile(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b'), 'dmy'),
    # YYYY-MM-DD or YYYY/MM/DD
    (re.compile(r'\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b'), 'ymd'),
    # DD-MM-YY or DD/MM/YY
    (re.compile(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})\b'), 'dmy2'),
    # DD MONTH YYYY  e.g. 23 JAN 2019 or 23-JAN-2019
    (re.compile(r'\b(\d{1,2})[-\s/.]+([A-Za-z]{3,9})[-\s/.]+(\d{2,4})\b'), 'dmony'),
    # MONTH DD YYYY
    (re.compile(r'\b([A-Za-z]{3,9})\s+(\d{1,2})[,\s]+(\d{2,4})\b'), 'mondy'),
]

MONTHS = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'SEPT': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
    'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4, 'JUNE': 6,
    'JULY': 7, 'AUGUST': 8, 'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12,
}


def valid_date(y, m, d):
    if not (1 <= m <= 12):
        return False
    if not (1 <= d <= 31):
        return False
    if not (2000 <= y <= 2099 or 1990 <= y <= 2099):
        return False
    # month-specific day check
    import calendar
    try:
        if d > calendar.monthrange(y, m)[1]:
            return False
    except Exception:
        return False
    return True


def find_date(text: str):
    for line in text.splitlines():
        for pat, kind in DATE_PATTERNS:
            for m in pat.finditer(line):
                try:
                    if kind == 'dmy':
                        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    elif kind == 'ymd':
                        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    elif kind == 'dmy2':
                        d, mo, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
                        y = 2000 + yy if yy < 70 else 1900 + yy
                    elif kind == 'dmony':
                        d = int(m.group(1))
                        mon = m.group(2).upper()
                        if mon not in MONTHS:
                            continue
                        mo = MONTHS[mon]
                        yy = int(m.group(3))
                        y = yy if yy >= 1000 else (2000 + yy if yy < 70 else 1900 + yy)
                    elif kind == 'mondy':
                        mon = m.group(1).upper()
                        if mon not in MONTHS:
                            continue
                        mo = MONTHS[mon]
                        d = int(m.group(2))
                        yy = int(m.group(3))
                        y = yy if yy >= 1000 else (2000 + yy if yy < 70 else 1900 + yy)
                    else:
                        continue
                    if valid_date(y, mo, d):
                        return f"{y:04d}-{mo:02d}-{d:02d}"
                except Exception:
                    continue
    return None


def ocr_variants(image_path: str):
    img = Image.open(image_path)
    gray = ImageOps.grayscale(img)
    w, h = img.size
    variants = [
        img,
        ImageOps.autocontrast(gray),
        gray.filter(ImageFilter.SHARPEN),
        ImageOps.autocontrast(img.resize((w * 2, h * 2), Image.LANCZOS).convert('L')),
    ]
    texts = []
    psm_modes = ['--psm 6', '--psm 4', '--psm 11']
    for v in variants:
        for psm in psm_modes:
            try:
                t = pytesseract.image_to_string(v, config=psm)
                if t.strip():
                    texts.append(t)
            except Exception:
                pass
    return texts


def process_image(image_path: str):
    texts = ocr_variants(image_path)

    # Value-level voting for total
    total_votes = {}
    for t in texts:
        amt = find_total(t)
        if amt is not None:
            key = f"{amt:.2f}"
            total_votes[key] = total_votes.get(key, 0) + 1

    # Value-level voting for date
    date_votes = {}
    for t in texts:
        d = find_date(t)
        if d is not None:
            date_votes[d] = date_votes.get(d, 0) + 1

    best_total = max(total_votes.items(), key=lambda x: x[1])[0] if total_votes else None
    best_date = max(date_votes.items(), key=lambda x: x[1])[0] if date_votes else None

    return best_date, best_total


def main():
    files = sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png')))
    results = []
    for fn in files:
        path = os.path.join(IMG_DIR, fn)
        try:
            d, t = process_image(path)
        except Exception as e:
            print(f"ERROR on {fn}: {e}")
            d, t = None, None
        print(f"{fn}: date={d}, total={t}")
        results.append((fn, d, t))

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for fn, d, t in results:
        ws.append([fn, d, t])
    wb.save(OUT_XLSX)
    print(f"Saved to {OUT_XLSX}")


if __name__ == "__main__":
    main()
