import os
import re
import pytesseract
from PIL import Image, ImageOps
from collections import Counter
from openpyxl import Workbook

IMG_DIR = '/app/workspace/dataset/img'
OUT_FILE = '/app/workspace/stat_ocr.xlsx'

PRIORITY = [
    ['GRAND TOTAL', 'GRANDTOTAL'],
    ['TOTAL RM', 'TOTAL: RM'],
    ['TOTAL AMOUNT'],
    ['TOTAL DUE', 'AMOUNT DUE', 'BALANCE DUE', 'NETT TOTAL', 'NET TOTAL', 'TOTAL', 'AMOUNT'],
]
EXCL_HARD = ['SUBTOTAL', 'SUB TOTAL', 'SUB-TOTAL', 'TAX', 'DISCOUNT', 'CHANGE', 'CASH TENDERED']


def ocr(img_path, scale=2, psm=6):
    img = Image.open(img_path)
    if scale != 1:
        w, h = img.size
        img = img.resize((w * scale, h * scale), Image.LANCZOS)
    gray = ImageOps.autocontrast(ImageOps.grayscale(img))
    return pytesseract.image_to_string(gray, config=f'--psm {psm}')


def normalize(line):
    return re.sub(r'[^A-Z0-9 ]', ' ', line.upper())


def contains_phrase(norm_line, phrase):
    if ' ' in phrase:
        tokens = phrase.split()
        pattern = r'\b' + r'\s+'.join(re.escape(t) for t in tokens) + r'\b'
    else:
        pattern = r'\b' + re.escape(phrase) + r'\b'
    return re.search(pattern, norm_line) is not None


def _clean_line(line):
    return re.sub(r'(\d)\.\s+(\d{2})\b', r'\1.\2', line)


def all_amounts(line):
    return re.findall(r'-?\d{1,3}(?:,\d{3})*\.\d{2}', _clean_line(line))


def amount_at_end(line):
    stripped = _clean_line(line).rstrip()
    return re.search(r'-?\d{1,3}(?:,\d{3})*\.\d{2}$', stripped) is not None


def find_total(text):
    lines = [l for l in text.split('\n') if l.strip()]
    norm_lines = [(l, normalize(l)) for l in lines]
    for group in PRIORITY:
        candidates = []
        for line, nline in norm_lines:
            if not any(contains_phrase(nline, k) for k in group):
                continue
            if any(contains_phrase(nline, e) for e in EXCL_HARD):
                continue
            amounts = all_amounts(line)
            if not amounts:
                continue
            if group == PRIORITY[3]:
                if len(amounts) >= 2:
                    continue
                if not amount_at_end(line):
                    continue
            val = amounts[-1].replace(',', '').lstrip('-')
            has_gst = contains_phrase(nline, 'GST') or contains_phrase(nline, 'SST')
            candidates.append((val, has_gst))
        if candidates:
            non_gst = [c for c in candidates if not c[1]]
            pick = non_gst[-1] if non_gst else candidates[-1]
            return pick[0]
    return None


def parse_date(text):
    for m in re.finditer(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b', text):
        d_s, mo_s, y_s = m.group(1), m.group(2), m.group(3)
        try:
            d = int(d_s); mo = int(mo_s); y = int(y_s)
            if len(y_s) == 2:
                y += 2000
            if 1 <= d <= 31 and 1 <= mo <= 12 and 2000 <= y <= 2030:
                return f'{y:04d}-{mo:02d}-{d:02d}'
        except ValueError:
            pass
    return None


def format_amount(a):
    if a is None:
        return None
    try:
        return f'{float(a):.2f}'
    except ValueError:
        return None


def extract(img_path):
    configs = [(1, 6), (2, 6), (3, 6), (1, 4), (2, 4), (3, 4), (1, 3), (3, 3)]
    dates = []
    totals = []
    for scale, psm in configs:
        try:
            text = ocr(img_path, scale=scale, psm=psm)
        except Exception:
            continue
        d = parse_date(text)
        t = find_total(text)
        if d:
            dates.append(d)
        if t:
            totals.append(t)
    date = Counter(dates).most_common(1)[0][0] if dates else None
    total = Counter(totals).most_common(1)[0][0] if totals else None
    return date, format_amount(total)


def main():
    wb = Workbook()
    ws = wb.active
    ws.title = 'results'
    ws.append(['filename', 'date', 'total_amount'])

    files = sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png')))
    for fn in files:
        path = os.path.join(IMG_DIR, fn)
        date, total = extract(path)
        print(f'{fn}: date={date} total={total}')
        ws.append([fn, date, total])
    wb.save(OUT_FILE)


if __name__ == '__main__':
    main()
