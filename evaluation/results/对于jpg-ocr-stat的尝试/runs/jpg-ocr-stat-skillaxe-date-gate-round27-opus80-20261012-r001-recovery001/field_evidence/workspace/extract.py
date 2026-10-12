#!/usr/bin/env python3
"""Extract date & total_amount from receipt images → /app/workspace/stat_ocr.xlsx."""
import os
import re
import json
import glob
from datetime import datetime
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps, ImageFilter
from openpyxl import Workbook

IMG_DIR = "/app/workspace/dataset/img"
OUT_XLSX = "/app/workspace/stat_ocr.xlsx"

# ---------- OCR helpers ----------

CACHE_DIR = "/app/workspace/.ocr_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def ocr_variants(path):
    """Run OCR with several preprocessing variants + PSM modes, return list of texts (cached)."""
    cache_file = os.path.join(CACHE_DIR, os.path.basename(path) + ".json")
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)
    img = Image.open(path)
    gray = ImageOps.grayscale(img)
    w, h = img.size
    variants = [
        ImageOps.autocontrast(gray),
        ImageOps.invert(ImageOps.autocontrast(gray)),
        gray.filter(ImageFilter.SHARPEN),
        ImageOps.autocontrast(img.resize((w * 2, h * 2), Image.LANCZOS).convert('L')),
        ImageOps.autocontrast(img.resize((w * 3, h * 3), Image.LANCZOS).convert('L')),
    ]
    psm_modes = ['--psm 6', '--psm 4', '--psm 11']
    texts = []
    for v in variants:
        for psm in psm_modes:
            try:
                t = pytesseract.image_to_string(v, config=psm)
                if t.strip():
                    texts.append(t)
            except Exception:
                pass
    with open(cache_file, 'w') as f:
        json.dump(texts, f)
    return texts

# ---------- Amount parsing ----------

MONEY_STRICT = re.compile(r'(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})(?![\d.])')

def _repair_line(s):
    """Normalize OCR glitches so dot-decimals re-match."""
    s = str(s).replace('"', '').replace('~', '').replace('—', '')
    # Collapse space right after a decimal dot: "85. 54" -> "85.54"
    s = re.sub(r'(\d)\.\s+(\d{2})\b', r'\1.\2', s)
    # Colon-as-decimal: "92:80" -> "92.80"
    s = re.sub(r'(\d)[:](\d{2})\b', r'\1.\2', s)
    # Bare "d+,dd" at a token boundary -> "d+.dd" (comma mis-read as dot).
    # Only apply when the comma is followed by exactly 2 digits and not followed
    # by more digits (so "1,234.56" is left alone).
    s = re.sub(r'(?<![\d,])(\d{1,3}),(\d{2})(?![\d,])', r'\1.\2', s)
    return s

def line_last_money(line):
    """Return last well-formed money token on the line (float) or None."""
    s = _repair_line(line)
    matches = list(MONEY_STRICT.finditer(s))
    if matches:
        m = matches[-1]
        return float(m.group(1).replace(',', '') + '.' + m.group(2))
    # Space-as-decimal fallback: "92 80" -> "92.80"
    s2 = re.sub(r'(\d)\s+(\d{2})\b', r'\1.\2', s)
    matches = list(MONEY_STRICT.finditer(s2))
    if matches:
        m = matches[-1]
        return float(m.group(1).replace(',', '') + '.' + m.group(2))
    return None

def parse_money(token):
    return line_last_money(token) if token is not None else None

# Priority tiers (higher = more specific). TOTAL ranks above bare AMOUNT.
KEYWORD_TIERS = [
    (5, [r'GRAND\s*TOTAL']),
    (4, [r'TOTAL\s*:?\s*RM']),
    (3, [r'TOTAL\s+AMOUNT']),
    (2, [r'TOTAL\s+DUE', r'AMOUNT\s+DUE', r'BALANCE\s+DUE',
         r'NETT?\s+TOTAL', r'\bTOTAL\b']),
    (1, [r'\bAMOUNT\b']),
]

# Exclusion patterns: skip a line iff the keyword appears BEFORE the TOTAL/AMOUNT keyword.
EXCLUDE_BEFORE_PATTERNS = [
    r'SUB[\s\-]*TOTAL',
    r'TAX',
    r'GST',
    r'SST',
    r'DISCOUNT',
    r'CHANGE',
    r'CASH\s+TENDERED',
    r'ROUNDING',
    r'\bQTY\b',   # column headers like "QTY ITEM TOTAL"
    r'SUMMARY',   # GST SUMMARY section header
]

# Exclusion patterns: skip the line if these appear ANYWHERE on it.
EXCLUDE_ANYWHERE_PATTERNS = [
    r'EXCL',                 # "Total Excluding GST", "Amt Excl GST"
    r'SERV[\.\s]*CHARGE',    # "Serv. Charge (3%)"
    r'TOTAL\s+(?:GST|TAX|SST)\b',    # "Total GST", "Total TAX"
    r'(?:GST|TAX|SST)\s+TOTAL\b',    # "GST TOTAL", "TAX TOTAL"
    # "TOTAL INCLUDES ... %GST <number>" — the <number> is the tax amount, not the total.
    r'INCLUDES?\b.*\bGST\b\s*\d',
]

def find_amount(text):
    """Scan text lines, return best candidate (float) using priority rules."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    best = None  # (tier, line_index, value)
    in_summary = False
    for i, line in enumerate(lines):
        up = line.upper()
        if not up.strip():
            continue
        # Enter "GST Summary" context — exclude everything after.
        if re.search(r'(?:GST|TAX)\s+SUMMARY', up) or re.search(r'\bSUMMARY\b', up):
            in_summary = True
            continue
        if in_summary:
            continue
        # Determine highest matching tier and its position
        matched_tier = 0
        kw_pos = None
        for tier, pats in KEYWORD_TIERS:
            for p in pats:
                m = re.search(p, up)
                if m:
                    matched_tier = tier
                    kw_pos = m.start()
                    break
            if matched_tier:
                break
        if matched_tier == 0:
            continue
        # Exclusions (not applied to GRAND TOTAL).
        if matched_tier < 5:
            excluded = False
            for p in EXCLUDE_BEFORE_PATTERNS:
                m = re.search(p, up)
                if m and m.start() <= kw_pos:
                    excluded = True
                    break
            if not excluded:
                for p in EXCLUDE_ANYWHERE_PATTERNS:
                    if re.search(p, up):
                        excluded = True
                        break
            if excluded:
                continue

        val = line_last_money(line)
        if val is None:
            # Fallback: use the FIRST non-blank line after the keyword, iff it
            # isn't itself excluded. Stop at the first non-blank line regardless.
            for j in range(i + 1, min(i + 3, len(lines))):
                nxt = lines[j]
                if not nxt.strip():
                    continue
                nxt_up = nxt.upper()
                if any(re.search(p, nxt_up) for p in EXCLUDE_BEFORE_PATTERNS) or \
                   any(re.search(p, nxt_up) for p in EXCLUDE_ANYWHERE_PATTERNS):
                    break
                v2 = line_last_money(nxt)
                if v2 is not None:
                    val = v2
                break
        if val is None:
            continue
        # Prefer higher tier; within same tier, keep the LAST match
        # (the final grand total is usually at the bottom of the receipt).
        if best is None or matched_tier > best[0] or (matched_tier == best[0] and i > best[1]):
            best = (matched_tier, i, val)
    return best[2] if best else None

def extract_amount(texts):
    """Vote across OCR variants."""
    candidates = []
    for t in texts:
        v = find_amount(t)
        if v is not None:
            candidates.append(round(v, 2))
    if not candidates:
        return None
    # Majority vote
    from collections import Counter
    cnt = Counter(candidates)
    best_val, _ = cnt.most_common(1)[0]
    return best_val

# ---------- Date parsing ----------

DATE_PATTERNS = [
    # dd/mm/yyyy or dd-mm-yyyy or dd.mm.yyyy
    (re.compile(r'(?<!\d)(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})(?!\d)'), 'dmy'),
    # yyyy/mm/dd or yyyy-mm-dd
    (re.compile(r'(?<!\d)(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})(?!\d)'), 'ymd'),
]

MONTH_NAMES = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'SEPT': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
    'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4, 'JUNE': 6,
    'JULY': 7, 'AUGUST': 8, 'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12,
}

DATE_TEXT_RE = re.compile(
    r'(?<!\d)(\d{1,2})[\-\s/]*([A-Za-z]{3,9})[\-\s/,]*(\d{2,4})(?!\d)'
)
DATE_TEXT_RE2 = re.compile(
    r'(?<!\d)([A-Za-z]{3,9})[\-\s/]*(\d{1,2})[\-\s/,]*(\d{2,4})(?!\d)'
)

def normalize_year(y):
    y = int(y)
    if y < 100:
        y = 2000 + y if y < 70 else 1900 + y
    return y

def try_make_date(y, m, d):
    try:
        y = normalize_year(y)
        return datetime(y, int(m), int(d)).date()
    except Exception:
        return None

def find_dates(text):
    """Return list of candidate date strings in ISO format."""
    results = []
    for pat, order in DATE_PATTERNS:
        for m in pat.finditer(text):
            a, b, c = m.group(1), m.group(2), m.group(3)
            if order == 'dmy':
                d, mo, y = a, b, c
                # Try d/m/y first
                dt = try_make_date(y, mo, d)
                if dt is None:
                    # fallback m/d/y
                    dt = try_make_date(y, d, mo)
            else:
                y, mo, d = a, b, c
                dt = try_make_date(y, mo, d)
            if dt and 2000 <= dt.year <= 2030:
                results.append(dt.isoformat())
    for m in DATE_TEXT_RE.finditer(text):
        d, mon_name, y = m.group(1), m.group(2).upper(), m.group(3)
        if mon_name in MONTH_NAMES:
            dt = try_make_date(y, MONTH_NAMES[mon_name], d)
            if dt and 2000 <= dt.year <= 2030:
                results.append(dt.isoformat())
    for m in DATE_TEXT_RE2.finditer(text):
        mon_name, d, y = m.group(1).upper(), m.group(2), m.group(3)
        if mon_name in MONTH_NAMES:
            dt = try_make_date(y, MONTH_NAMES[mon_name], d)
            if dt and 2000 <= dt.year <= 2030:
                results.append(dt.isoformat())
    return results

def extract_date(texts):
    from collections import Counter
    all_dates = []
    for t in texts:
        all_dates.extend(find_dates(t))
    if not all_dates:
        return None
    cnt = Counter(all_dates)
    return cnt.most_common(1)[0][0]

# ---------- Main ----------

def process_image(path):
    texts = ocr_variants(path)
    amount = extract_amount(texts)
    date = extract_date(texts)
    return date, amount, texts

def main():
    files = sorted(glob.glob(os.path.join(IMG_DIR, '*.jpg')))
    rows = []
    debug = {}
    for f in files:
        name = os.path.basename(f)
        print(f"Processing {name}...", flush=True)
        date, amount, texts = process_image(f)
        amount_str = f"{amount:.2f}" if amount is not None else None
        rows.append((name, date, amount_str))
        debug[name] = {
            'date': date,
            'amount': amount_str,
            'texts_count': len(texts),
        }
        print(f"  -> date={date}, amount={amount_str}", flush=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for name, date, amount_str in rows:
        ws.append([name, date, amount_str])
    wb.save(OUT_XLSX)
    print(f"Saved {OUT_XLSX}")

    with open('/app/workspace/debug.json', 'w') as f:
        json.dump(debug, f, indent=2)

if __name__ == '__main__':
    main()
