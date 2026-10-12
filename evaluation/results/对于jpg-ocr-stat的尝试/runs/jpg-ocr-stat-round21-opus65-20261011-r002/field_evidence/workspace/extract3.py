import os
import re
import pytesseract
from PIL import Image, ImageOps
from openpyxl import Workbook

IMG_DIR = '/app/workspace/dataset/img'
OUT_FILE = '/app/workspace/stat_ocr.xlsx'

PRIORITY_GROUPS = [
    ['GRAND TOTAL'],
    ['TOTAL RM', 'TOTAL: RM'],
    ['TOTAL AMOUNT'],
    ['TOTAL', 'AMOUNT', 'TOTAL DUE', 'AMOUNT DUE',
     'BALANCE DUE', 'NETT TOTAL', 'NET TOTAL'],
]

AMOUNT_RE = re.compile(r'(?<![\d.])(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})(?![\d])')
NUMBER_IN_LINE_RE = re.compile(r'\d[\d,]*\.\d{2}')


def ocr_variants(path):
    img = Image.open(path)
    yield pytesseract.image_to_string(img, config='--psm 6')
    yield pytesseract.image_to_string(img, config='--psm 4')
    yield pytesseract.image_to_string(img, config='--psm 3')
    w, h = img.size
    big2 = img.resize((w * 2, h * 2), Image.LANCZOS)
    big2 = ImageOps.grayscale(big2)
    big2 = ImageOps.autocontrast(big2)
    yield pytesseract.image_to_string(big2, config='--psm 6')
    yield pytesseract.image_to_string(big2, config='--psm 4')
    big3 = img.resize((w * 3, h * 3), Image.LANCZOS)
    big3 = ImageOps.grayscale(big3)
    big3 = ImageOps.autocontrast(big3)
    yield pytesseract.image_to_string(big3, config='--psm 6')
    yield pytesseract.image_to_string(big3, config='--psm 4')


def parse_amount_token(tok):
    try:
        return float(tok.replace(',', ''))
    except ValueError:
        return None


def kw_present(line_upper, kw):
    return re.search(r'(?<![A-Z])' + re.escape(kw) + r'(?![A-Z])', line_upper) is not None


def should_skip_line(line_upper, matched_kw):
    # Skip subtotal/change/discount/cash-tendered when the match is generic.
    for kw in ('SUBTOTAL', 'SUB TOTAL', 'CHANGE', 'CASH TENDERED', 'DISCOUNT'):
        if kw_present(line_upper, kw):
            # Even for GRAND TOTAL etc., these mean the line is really a
            # change/discount line (not a grand total).
            return True
    # Handle TAX/GST/SST:
    tax_present = any(kw_present(line_upper, k) for k in ('TAX', 'GST', 'SST'))
    if not tax_present:
        return False
    # If the matched keyword is itself a TAX/GST/SST compound (like "Total GST"),
    # exclude: pattern TOTAL immediately followed by tax word.
    if re.search(r'\bTOTAL\s+(?:GST|TAX|SST)\b', line_upper):
        return True
    # If the line is like "TAX AMOUNT" or "AMOUNT TAX" header without numbers,
    # we'll filter by requiring a same-line number below.
    return False


GST_SUMMARY_RE = re.compile(
    r'\b(?:GST|TAX)\s+(?:SUMMARY|TOTALS?|CODE|RATE)\b'
    r'|\bSUMMARY\s+AMOUNT\b'
    r'|\bAMOUNT\s*\(RM\)\s*TAX\b',
    re.IGNORECASE)


def extract_total(text):
    """Return (priority_index, same_line_flag, value) or (None, None, None).

    same_line_flag: 0 if value was on the same line as the keyword, 1 if from
    a fallback next-line.
    """
    lines = [l for l in text.splitlines() if l.strip()]
    for idx, line in enumerate(lines):
        if GST_SUMMARY_RE.search(line):
            lines = lines[:idx]
            break
    for p_idx, group in enumerate(PRIORITY_GROUPS):
        same_line_candidates = []
        fallback_candidates = []
        for i, line in enumerate(lines):
            up = line.upper()
            matched_kw = None
            for kw in group:
                if kw_present(up, kw):
                    matched_kw = kw
                    break
            if not matched_kw:
                continue
            if should_skip_line(up, matched_kw):
                continue

            nums = AMOUNT_RE.findall(line)
            if nums:
                val = parse_amount_token(nums[-1])
                if val is not None:
                    same_line_candidates.append((i, val))
            else:
                if not re.search(r'\d', line) and i + 1 < len(lines):
                    nxt_nums = NUMBER_IN_LINE_RE.findall(lines[i + 1])
                    if nxt_nums:
                        val = parse_amount_token(nxt_nums[-1])
                        if val is not None:
                            fallback_candidates.append((i, val))
        if same_line_candidates:
            return (p_idx, 0, same_line_candidates[-1][1])
        if fallback_candidates:
            return (p_idx, 1, fallback_candidates[-1][1])
    return (None, None, None)


DATE_PATTERNS = [
    (re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})'), 'dmy4'),
    (re.compile(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})'), 'ymd'),
    (re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2})(?!\d)'), 'dmy2'),
]


COMPACT_DATE_RE = re.compile(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)')


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
    # Fallback: look for YYYYMMDD compact pattern in INVOICE/BILL/TRANS lines.
    for line in lines:
        up = line.upper()
        if not any(k in up for k in ('INVOICE', 'BILL', 'TRANS', 'INV#', 'DOC')):
            continue
        for m in re.finditer(r'(20\d{2})(\d{2})(\d{2})', line):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31 and 2017 <= y <= 2020:
                return f'{y:04d}-{mo:02d}-{d:02d}'
    return None


def pick_consistent(values):
    """values: list of scalars or Nones. Pick most-frequent non-null; ties go
    to earliest."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return None
    best = None
    best_count = 0
    for v in non_null:
        c = non_null.count(v)
        if c > best_count:
            best_count = c
            best = v
    return best


def pick_total(results):
    """results: list of (priority, same_line_flag, value) tuples.

    Prefer most-specific priority (lowest index), then same-line over
    fallback, then mode of values.
    """
    non_null = [(p, s, v) for p, s, v in results if v is not None]
    if not non_null:
        return None
    best_p = min(p for p, _, _ in non_null)
    at_prio = [(s, v) for p, s, v in non_null if p == best_p]
    best_s = min(s for s, _ in at_prio)
    values = [v for s, v in at_prio if s == best_s]
    return pick_consistent(values)


def main():
    wb = Workbook()
    ws = wb.active
    ws.title = 'results'
    ws.append(['filename', 'date', 'total_amount'])

    for fname in sorted(os.listdir(IMG_DIR)):
        path = os.path.join(IMG_DIR, fname)
        dates, totals = [], []
        for text in ocr_variants(path):
            dates.append(extract_date(text))
            totals.append(extract_total(text))
        date = pick_consistent(dates)
        total = pick_total(totals)
        total_s = f'{total:.2f}' if total is not None else None
        print(f'{fname}: date={date}, total={total_s}  (d={dates} t={totals})')
        ws.append([fname, date, total_s])

    wb.save(OUT_FILE)


if __name__ == '__main__':
    main()
