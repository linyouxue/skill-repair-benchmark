import os
import re
import pytesseract
from PIL import Image, ImageOps
from openpyxl import Workbook

IMG_DIR = '/app/workspace/dataset/img'
OUT_FILE = '/app/workspace/stat_ocr.xlsx'

EXCLUDE_KEYWORDS = [
    'SUBTOTAL', 'SUB TOTAL', 'TAX', 'GST', 'SST', 'DISCOUNT',
    'CHANGE', 'CASH TENDERED',
]

PRIORITY_GROUPS = [
    ['GRAND TOTAL'],
    ['TOTAL RM', 'TOTAL: RM'],
    ['TOTAL AMOUNT'],
    ['TOTAL', 'AMOUNT', 'TOTAL DUE', 'AMOUNT DUE',
     'BALANCE DUE', 'NETT TOTAL', 'NET TOTAL'],
]

TOTAL_LIKE = {'TOTAL', 'AMOUNT', 'BALANCE', 'GRAND', 'NET', 'NETT'}

AMOUNT_RE = re.compile(r'(?<![\d.])(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})(?![\d])')
NUMBER_IN_LINE_RE = re.compile(r'\d[\d,]*\.\d{2}')


def ocr_variants(path):
    img = Image.open(path)
    yield pytesseract.image_to_string(img, config='--psm 6')
    w, h = img.size
    big = img.resize((w * 2, h * 2))
    big = ImageOps.grayscale(big)
    big = ImageOps.autocontrast(big)
    yield pytesseract.image_to_string(big, config='--psm 6')


def parse_amount_token(tok):
    tok = tok.replace(',', '')
    try:
        return float(tok)
    except ValueError:
        return None


def line_total_like(line_upper):
    for word in TOTAL_LIKE:
        if re.search(r'(?<![A-Z])' + word + r'(?![A-Z])', line_upper):
            return True
    return False


def line_has_excluded(line_upper):
    for kw in EXCLUDE_KEYWORDS:
        pattern = r'(?<![A-Z])' + re.escape(kw) + r'(?![A-Z])'
        if re.search(pattern, line_upper):
            return True
    return False


def extract_total(text):
    lines = [l for l in text.splitlines() if l.strip()]
    for group in PRIORITY_GROUPS:
        candidates = []
        for i, line in enumerate(lines):
            up = line.upper()
            matched_kw = None
            for kw in group:
                pattern = r'(?<![A-Z])' + re.escape(kw) + r'(?![A-Z])'
                if re.search(pattern, up):
                    matched_kw = kw
                    break
            if not matched_kw:
                continue

            # Exclude line only when the exclude word is the "primary" meaning,
            # i.e. the line is not also a TOTAL/AMOUNT-style final line.
            if line_has_excluded(up):
                # For specific keywords (GRAND TOTAL, TOTAL RM, NET/NETT TOTAL),
                # keep the match regardless; these labels are specific enough.
                specific = matched_kw in (
                    'GRAND TOTAL', 'TOTAL RM', 'TOTAL: RM',
                    'NET TOTAL', 'NETT TOTAL', 'TOTAL AMOUNT',
                )
                if not specific:
                    # For generic TOTAL/AMOUNT: skip when the line's dominant
                    # content is SUBTOTAL, CHANGE, CASH TENDERED, DISCOUNT.
                    # These are mutually exclusive with the final total.
                    dominant_exclude = any(
                        re.search(r'(?<![A-Z])' + re.escape(k) + r'(?![A-Z])', up)
                        for k in ('SUBTOTAL', 'SUB TOTAL', 'CHANGE',
                                  'CASH TENDERED', 'DISCOUNT')
                    )
                    if dominant_exclude:
                        continue
                    # If only TAX/GST/SST appear, allow if the line is total-like
                    # (e.g. "Total Incl. of GST 102.00").
                    if not line_total_like(up):
                        continue

            nums = AMOUNT_RE.findall(line)
            if nums:
                val = parse_amount_token(nums[-1])
                if val is not None:
                    candidates.append((i, val))
            else:
                if i + 1 < len(lines):
                    nxt_nums = NUMBER_IN_LINE_RE.findall(lines[i + 1])
                    if nxt_nums:
                        val = parse_amount_token(nxt_nums[-1])
                        if val is not None:
                            candidates.append((i, val))
        if candidates:
            return candidates[-1][1]
    return None


DATE_PATTERNS = [
    (re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})'), 'dmy4'),
    (re.compile(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})'), 'ymd'),
    (re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2})(?!\d)'), 'dmy2'),
]


def extract_date(text):
    lines = text.splitlines()
    ordered = sorted(enumerate(lines),
                     key=lambda x: (0 if 'DATE' in x[1].upper() else 1, x[0]))
    for _, line in ordered:
        for pat, kind in DATE_PATTERNS:
            for m in pat.finditer(line):
                a, b, c = m.group(1), m.group(2), m.group(3)
                if kind == 'dmy4':
                    d, mo, y = int(a), int(b), int(c)
                elif kind == 'ymd':
                    y, mo, d = int(a), int(b), int(c)
                else:
                    d, mo, y = int(a), int(b), int(c)
                    y = 2000 + y if y < 70 else 1900 + y
                if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2099:
                    return f'{y:04d}-{mo:02d}-{d:02d}'
    return None


def pick_consistent(values):
    """Pick a value, preferring the first OCR variant, else the one agreeing."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return None
    # If any value appears more than once, prefer that
    for v in non_null:
        if non_null.count(v) > 1:
            return v
    return non_null[0]


def main():
    wb = Workbook()
    ws = wb.active
    ws.title = 'results'
    ws.append(['filename', 'date', 'total_amount'])

    for fname in sorted(os.listdir(IMG_DIR)):
        path = os.path.join(IMG_DIR, fname)
        dates = []
        totals = []
        for text in ocr_variants(path):
            dates.append(extract_date(text))
            totals.append(extract_total(text))
        date = pick_consistent(dates)
        total = pick_consistent(totals)
        total_s = f'{total:.2f}' if total is not None else None
        print(f'{fname}: date={date}, total={total_s}  (variants d={dates} t={totals})')
        ws.append([fname, date, total_s])

    wb.save(OUT_FILE)
    print(f'Saved to {OUT_FILE}')


if __name__ == '__main__':
    main()
