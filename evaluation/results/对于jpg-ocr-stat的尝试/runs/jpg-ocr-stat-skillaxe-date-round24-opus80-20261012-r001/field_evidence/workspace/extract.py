import os
import re
import pytesseract
from PIL import Image, ImageOps
from decimal import Decimal
from collections import Counter
from openpyxl import Workbook

IMG_DIR = '/app/workspace/dataset/img'
OUT_XLSX = '/app/workspace/stat_ocr.xlsx'

EXCLUDE_KWS = [
    'SUBTOTAL', 'SUB TOTAL', 'SUB-TOTAL',
    'TAX', 'GST', 'SST',
    'DISCOUNT', 'CHANGE', 'CASH TENDERED',
]

# Priority tiers (specific -> generic)
PRIORITY_TIERS = [
    ['GRAND TOTAL'],
    ['TOTAL RM', 'TOTAL: RM'],
    ['TOTAL AMOUNT'],
    ['TOTAL DUE', 'AMOUNT DUE', 'BALANCE DUE', 'NETT TOTAL', 'NET TOTAL', 'TOTAL', 'AMOUNT'],
]

# Money token: X.XX or X,XXX.XX (positive only; we don't treat refunds/payments as totals)
MONEY_RE = re.compile(r'(?<![\d.-])(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})(?!\d)')

# Repairable "D DD" at end of segment -> "D.DD"; limit integer part to <=4 to
# avoid clobbering 4-digit years in next-line fallbacks.
SPACE_DEC_RE = re.compile(r'(?<!\d)(\d{1,4})\s+(\d{2})(?!\d)')
# Repairable "D,DD" when no dot nearby (European-style decimal from OCR)
COMMA_DEC_RE = re.compile(r'(?<!\d)(\d{1,4}),(\d{2})(?!\d)')


def ocr_variants(img_path):
    img = Image.open(img_path)
    gray = ImageOps.grayscale(img)
    w, h = img.size
    big = img.resize((w*3, h*3), Image.LANCZOS).convert('L')
    variants = [
        (img, '--psm 6'),
        (img, '--psm 4'),
        (ImageOps.autocontrast(gray), '--psm 6'),
        (ImageOps.autocontrast(big), '--psm 6'),
        (ImageOps.autocontrast(big), '--psm 4'),
    ]
    texts = []
    for v, psm in variants:
        try:
            texts.append(pytesseract.image_to_string(v, config=psm))
        except Exception:
            texts.append('')
    return texts


# Normalize an uppercase line to improve exclusion keyword detection
# against common OCR confusions (6<->G, 5<->S, 1<->I).
def normalize_for_exclusion(line_upper):
    s = line_upper
    # Only substitute within letter-ish contexts: replace digits that are
    # directly adjacent to letters with their letter counterpart.
    # Simple approach: do a few global replacements guarded by letter neighbors.
    s = re.sub(r'(?<=[A-Z])6(?=[A-Z])', 'G', s)
    s = re.sub(r'(?<=[A-Z])5(?=[A-Z])', 'S', s)
    s = re.sub(r'(?<=[A-Z])1(?=[A-Z])', 'I', s)
    s = re.sub(r'(?<=[A-Z])0(?=[A-Z])', 'O', s)
    s = re.sub(r'6(?=ST\b)', 'G', s)  # 6ST -> GST
    s = re.sub(r'G5T\b', 'GST', s)
    s = re.sub(r'GS[I1]\b', 'GST', s)
    return s


def is_excluded(line_upper):
    """Return True if the line is a subtotal/tax/change/discount line.

    We require the exclusion keyword to appear at the start of the line
    (after any leading non-letter chars). This keeps real total lines like
    "Total Sales (Inclusive GST) RM 9.90" from being filtered out just
    because they mention GST parenthetically, while still skipping true
    "Sub-total 15.00", "GST 6% ...", "Change ..." etc.
    """
    norm = normalize_for_exclusion(line_upper)
    stripped = re.sub(r'^[^A-Z]*', '', norm)
    for kw in EXCLUDE_KWS:
        if stripped.startswith(kw):
            return True
    # Also exclude "CASH TENDERED" anywhere (less common but specific).
    if 'CASH TENDERED' in norm:
        return True
    return False


def parse_money(tok):
    s = tok.replace(',', '')
    try:
        return Decimal(s)
    except Exception:
        return None


def repair_line_money(text):
    """Apply OCR repairs for monetary tokens on a *keyword-matched* line only.

    - '92 80' -> '92.80'
    - '99,80' (comma-as-decimal) -> '99.80' when no dot already present
    """
    repaired = SPACE_DEC_RE.sub(r'\1.\2', text)
    if '.' not in repaired:
        repaired = COMMA_DEC_RE.sub(r'\1.\2', repaired)
    return repaired


# Detect a line that looks like a GST breakdown row: multiple money tokens on
# the same line (e.g. "Total 16.71 0.99").
def is_gst_breakdown(line):
    moneys = MONEY_RE.findall(line)
    return len(moneys) >= 2


GST_SUMMARY_RE = re.compile(r'(?:GST|SST|TAX)\s+SUMMARY', re.IGNORECASE)
DATE_HINT_RE = re.compile(r'\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}')


def extract_total_from_text(text):
    lines = [l.rstrip() for l in text.splitlines()]
    upper = [l.upper() for l in lines]

    # Mark lines that follow a "GST Summary"/"Tax Summary" header as part of
    # the tax breakdown block (until the block ends with a blank line).
    in_summary_block = [False] * len(lines)
    active = False
    for i, ul in enumerate(upper):
        if GST_SUMMARY_RE.search(ul):
            active = True
            in_summary_block[i] = True
            continue
        if active:
            if not lines[i].strip():
                active = False
                continue
            in_summary_block[i] = True

    for tier in PRIORITY_TIERS:
        candidates = []  # list of (line_index, Decimal, from_same_line)
        for i, ul in enumerate(upper):
            if is_excluded(ul):
                continue
            if in_summary_block[i]:
                continue
            matched_kw = None
            for kw in tier:
                if kw in ul:
                    matched_kw = kw
                    break
            if not matched_kw:
                continue
            line = lines[i]
            # Skip GST-breakdown rows for generic TOTAL/AMOUNT (tier 4 only)
            if tier is PRIORITY_TIERS[-1] and is_gst_breakdown(line):
                continue
            # Same-line money (with repair)
            repaired = repair_line_money(line)
            moneys = MONEY_RE.findall(repaired)
            if moneys:
                d = parse_money(moneys[-1])
                if d is not None:
                    candidates.append((i, d, True))
                    continue
            # Fallback: next non-empty, non-excluded line (no repair; avoid
            # dates like "09/02/2018 12:53" becoming "2018.12")
            for j in range(i+1, min(i+4, len(lines))):
                nxt = lines[j]
                if not nxt.strip():
                    continue
                if is_excluded(upper[j]) or in_summary_block[j]:
                    break
                if DATE_HINT_RE.search(nxt):
                    break
                moneys_n = MONEY_RE.findall(nxt)
                if moneys_n:
                    d = parse_money(moneys_n[-1])
                    if d is not None:
                        candidates.append((i, d, False))
                else:
                    # last plain number on line
                    nums = re.findall(r'(?<!\d)\d+(?!\d)', nxt)
                    if nums:
                        try:
                            d = Decimal(nums[-1])
                            candidates.append((i, d, False))
                        except Exception:
                            pass
                break
        if candidates:
            # Prefer last same-line match; otherwise last fallback
            same_line = [c for c in candidates if c[2]]
            if same_line:
                return same_line[-1][1]
            return candidates[-1][1]
    return None


DATE_PATTERNS = [
    (re.compile(r'(?<!\d)(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{2,4})(?!\d)'), 'dmy'),
    (re.compile(r'(?<!\d)(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})(?!\d)'), 'ymd'),
    (re.compile(r'(?<!\w)(\d{1,2})[\s\-]+([A-Za-z]{3,9})[\s\-,]+(\d{2,4})(?!\d)'), 'dmony'),
    (re.compile(r'(?<!\w)([A-Za-z]{3,9})[\s\-]+(\d{1,2})[\s\-,]+(\d{2,4})(?!\d)'), 'mondy'),
]

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'SEPT': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
    'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4, 'JUNE': 6,
    'JULY': 7, 'AUGUST': 8, 'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12,
}


def normalize_year(y):
    y = int(y)
    if y < 100:
        y += 2000 if y < 70 else 1900
    return y


def try_date(text):
    for pat, kind in DATE_PATTERNS:
        for m in pat.finditer(text):
            try:
                if kind == 'dmy':
                    d, mo, y = int(m.group(1)), int(m.group(2)), normalize_year(m.group(3))
                    if 1 <= d <= 31 and 1 <= mo <= 12 and 2000 <= y <= 2099:
                        return f'{y:04d}-{mo:02d}-{d:02d}'
                elif kind == 'ymd':
                    y, mo, d = normalize_year(m.group(1)), int(m.group(2)), int(m.group(3))
                    if 1 <= d <= 31 and 1 <= mo <= 12 and 2000 <= y <= 2099:
                        return f'{y:04d}-{mo:02d}-{d:02d}'
                elif kind == 'dmony':
                    d = int(m.group(1)); mo = MONTH_MAP.get(m.group(2).upper()); y = normalize_year(m.group(3))
                    if mo and 1 <= d <= 31 and 2000 <= y <= 2099:
                        return f'{y:04d}-{mo:02d}-{d:02d}'
                elif kind == 'mondy':
                    mo = MONTH_MAP.get(m.group(1).upper()); d = int(m.group(2)); y = normalize_year(m.group(3))
                    if mo and 1 <= d <= 31 and 2000 <= y <= 2099:
                        return f'{y:04d}-{mo:02d}-{d:02d}'
            except Exception:
                continue
    return None


INVOICE_YMD_RE = re.compile(r'(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{6,}')


def try_invoice_date(text):
    for m in INVOICE_YMD_RE.finditer(text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f'{y:04d}-{mo:02d}-{d:02d}'
    return None


def extract_date_from_texts(texts):
    votes = Counter()
    for t in texts:
        d = try_date(t)
        if d:
            votes[d] += 1
    if votes:
        return votes.most_common(1)[0][0]
    # fallback: invoice-style
    for t in texts:
        d = try_invoice_date(t)
        if d:
            return d
    return None


def extract_total_from_texts(texts):
    votes = Counter()
    for t in texts:
        d = extract_total_from_text(t)
        if d is not None:
            votes[d] += 1
    if not votes:
        return None
    return votes.most_common(1)[0][0]


def main():
    rows = []
    for fn in sorted(os.listdir(IMG_DIR)):
        if not fn.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        path = os.path.join(IMG_DIR, fn)
        texts = ocr_variants(path)
        date = extract_date_from_texts(texts)
        total = extract_total_from_texts(texts)
        total_str = f'{total:.2f}' if total is not None else None
        rows.append((fn, date, total_str))
        print(fn, date, total_str)

    wb = Workbook()
    ws = wb.active
    ws.title = 'results'
    ws.append(['filename', 'date', 'total_amount'])
    for r in rows:
        ws.append(list(r))
    wb.save(OUT_XLSX)
    print('Saved', OUT_XLSX)


if __name__ == '__main__':
    main()
