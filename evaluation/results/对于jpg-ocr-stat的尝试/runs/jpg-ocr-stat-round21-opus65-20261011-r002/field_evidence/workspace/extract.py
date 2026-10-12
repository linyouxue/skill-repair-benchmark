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

AMOUNT_RE = re.compile(r'(?<![\d.])(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})(?![\d])')
NUMBER_IN_LINE_RE = re.compile(r'\d[\d,]*\.\d{2}')


def ocr_text(path):
    """Multi-pass OCR; return the best raw text (prefer upscaled + grayscale)."""
    img = Image.open(path)
    w, h = img.size
    big = img.resize((w * 2, h * 2))
    big = ImageOps.grayscale(big)
    big = ImageOps.autocontrast(big)
    txt = pytesseract.image_to_string(big, config='--psm 6')
    return txt


def parse_amount_token(tok):
    tok = tok.replace(',', '')
    try:
        return float(tok)
    except ValueError:
        return None


def line_has_excluded(line_upper):
    for kw in EXCLUDE_KEYWORDS:
        if kw in line_upper:
            # 'TOTAL' line could contain 'TAX' word etc. Only exclude if the
            # keyword is standalone (surrounded by non-letters).
            # Example: "GST @ 6%" vs "GST SUMMARY" vs "Including GST 6%".
            # Simpler: exclude if keyword present as a word.
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
            # Check whether this line matches any keyword in group
            matched_kw = None
            for kw in group:
                pattern = r'(?<![A-Z])' + re.escape(kw) + r'(?![A-Z])'
                if re.search(pattern, up):
                    matched_kw = kw
                    break
            if not matched_kw:
                continue
            # For lower-priority groups, apply exclusion keywords
            # (e.g. SUBTOTAL contains TOTAL)
            if line_has_excluded(up):
                # But if the matched keyword is more specific (GRAND TOTAL,
                # TOTAL RM, NET TOTAL, NETT TOTAL), allow it.
                if matched_kw in ('GRAND TOTAL', 'TOTAL RM', 'TOTAL: RM',
                                  'NET TOTAL', 'NETT TOTAL'):
                    pass
                else:
                    continue

            # Find number on this line
            nums = AMOUNT_RE.findall(line)
            if nums:
                val = parse_amount_token(nums[-1])
                if val is not None:
                    candidates.append((i, val))
            else:
                # Fallback: last number on next line
                if i + 1 < len(lines):
                    nxt_nums = NUMBER_IN_LINE_RE.findall(lines[i + 1])
                    if nxt_nums:
                        val = parse_amount_token(nxt_nums[-1])
                        if val is not None:
                            candidates.append((i, val))
        if candidates:
            # Return the last match in document order (final total)
            return candidates[-1][1]
    return None


DATE_PATTERNS = [
    re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})'),   # DD-MM-YYYY
    re.compile(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})'),   # YYYY-MM-DD
    re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2})\b'), # DD-MM-YY
]


def extract_date(text):
    # Prefer dates on lines mentioning "Date" first, else first plausible.
    lines = text.splitlines()
    ordered = sorted(lines, key=lambda l: 0 if 'DATE' in l.upper() else 1)
    for line in ordered:
        for pat_idx, pat in enumerate(DATE_PATTERNS):
            for m in pat.finditer(line):
                a, b, c = m.group(1), m.group(2), m.group(3)
                if pat_idx == 0:  # DD-MM-YYYY
                    d, mo, y = int(a), int(b), int(c)
                elif pat_idx == 1:  # YYYY-MM-DD
                    y, mo, d = int(a), int(b), int(c)
                else:  # DD-MM-YY
                    d, mo, y = int(a), int(b), int(c)
                    y = 2000 + y if y < 70 else 1900 + y
                if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2099:
                    return f'{y:04d}-{mo:02d}-{d:02d}'
    return None


def main():
    wb = Workbook()
    ws = wb.active
    ws.title = 'results'
    ws.append(['filename', 'date', 'total_amount'])

    for fname in sorted(os.listdir(IMG_DIR)):
        path = os.path.join(IMG_DIR, fname)
        text = ocr_text(path)
        date = extract_date(text)
        total = extract_total(text)
        total_s = f'{total:.2f}' if total is not None else None
        print(f'{fname}: date={date}, total={total_s}')
        ws.append([fname, date, total_s])

    wb.save(OUT_FILE)
    print(f'Saved to {OUT_FILE}')


if __name__ == '__main__':
    main()
