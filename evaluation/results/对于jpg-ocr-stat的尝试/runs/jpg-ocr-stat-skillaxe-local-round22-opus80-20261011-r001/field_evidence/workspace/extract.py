"""Extract date and total amount from scanned receipts and write to Excel."""
import os
import re
from collections import Counter

import pytesseract
from PIL import Image, ImageOps
from openpyxl import Workbook

IMG_DIR = "/app/workspace/dataset/img"
OUT_XLSX = "/app/workspace/stat_ocr.xlsx"

# Priority tiers (most specific first)
INCLUDE_TIERS = [
    ["GRAND TOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    ["TOTAL", "AMOUNT", "TOTAL DUE", "AMOUNT DUE", "BALANCE DUE", "NETT TOTAL", "NET TOTAL"],
]
EXCLUDE_KEYWORDS = [
    "SUBTOTAL", "SUB TOTAL", "TAX", "GST", "SST",
    "DISCOUNT", "CHANGE", "CASH TENDERED",
]

MONTHS = {m: i + 1 for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
     'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}


def normalize(s: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', s.upper())


def ocr_variants(img_path: str):
    """Return list of OCR text outputs from several preprocessing/PSM variants."""
    img = Image.open(img_path)
    w, h = img.size
    gray2 = ImageOps.autocontrast(img.resize((w * 2, h * 2), Image.LANCZOS).convert('L'))
    gray3 = ImageOps.autocontrast(img.resize((w * 3, h * 3), Image.LANCZOS).convert('L'))
    return [
        pytesseract.image_to_string(img),                       # 0: raw PSM 3
        pytesseract.image_to_string(gray2),                     # 1: 2x autocontrast PSM 3
        pytesseract.image_to_string(gray3, config='--psm 6'),   # 2: 3x autocontrast PSM 6
        pytesseract.image_to_string(gray2, config='--psm 6'),   # 3: 2x autocontrast PSM 6
        pytesseract.image_to_string(gray3),                     # 4: 3x autocontrast PSM 3
    ]


_MONEY_RE = re.compile(r'(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)\.(\d{1,2})(?![\d.])')


def _apply_decimal_repairs(line: str) -> str:
    """Return a copy of the line with likely OCR errors in money tokens repaired."""
    # Colon-as-decimal: '92:80' -> '92.80'
    out = re.sub(r'(\d)[:](\d{2})\b', r'\1.\2', line)
    # Comma-as-decimal: '21,30' -> '21.30' (but keep '1,234' with 3-digit thousands)
    out = re.sub(r'(\d),(\d{2})(?!\d)', r'\1.\2', out)
    # Space-as-decimal: '92 80' -> '92.80' (restrict to end-of-number context)
    out = re.sub(r'(\d)\s+(\d{2})(?!\d)', r'\1.\2', out)
    return out


def extract_amount_from_line(line: str):
    """Return the rightmost money value on the (OCR-repaired) line, or None."""
    repaired = _apply_decimal_repairs(line)
    cands = []
    for m in _MONEY_RE.finditer(repaired):
        try:
            cands.append(float(m.group(1).replace(',', '') + '.' + m.group(2).ljust(2, '0')))
        except ValueError:
            pass
    return cands[-1] if cands else None


def _match_pos(normalized_line: str, keywords):
    """Return earliest index at which any of ``keywords`` matches ``normalized_line``.

    ``keywords`` are plain strings, each normalised the same way as the line
    (uppercase alphanumeric only).
    """
    pos = -1
    for k in keywords:
        nk = normalize(k)
        if not nk:
            continue
        i = normalized_line.find(nk)
        if i != -1 and (pos == -1 or i < pos):
            pos = i
    return pos


def tier_candidates(text: str, tier_idx: int):
    """Return list of (line_index, amount) for all lines in the given tier."""
    keywords = INCLUDE_TIERS[tier_idx]
    lines = [ln for ln in text.splitlines() if ln.strip()]
    out = []
    for i, line in enumerate(lines):
        norm = normalize(line)
        inc_pos = _match_pos(norm, keywords)
        if inc_pos == -1:
            continue
        # Apply exclusion only when the exclusion keyword precedes the inclusion
        # keyword (i.e. it is the line's primary label).
        exc_pos = _match_pos(norm, EXCLUDE_KEYWORDS)
        if exc_pos != -1 and exc_pos < inc_pos:
            continue
        # Skip GST summary rows: in a GST summary block the preceding line is
        # a per-rate row (e.g. "SR @ 6% 16.71 0.99") and this "Total" line has
        # two monetary tokens (amount, tax). The payable amount in contrast
        # is written as "Total <RM X.YY>" with a single money token.
        if i > 0 and '%' in lines[i - 1]:
            money_count = len(list(_MONEY_RE.finditer(_apply_decimal_repairs(line))))
            if money_count >= 2:
                continue
        amt = extract_amount_from_line(line)
        if amt is None and i + 1 < len(lines):
            # Fallback: amount split onto the next line. Apply only when the
            # keyword line is a bare label (no digits) AND the next line looks
            # like just a monetary number (no label words). This avoids
            # accidentally picking up CASH/VISA/CHANGE values below a corrupted
            # keyword line.
            next_line = lines[i + 1]
            next_norm = normalize(next_line)
            next_has_label = _match_pos(next_norm, EXCLUDE_KEYWORDS) != -1
            if not any(ch.isdigit() for ch in line) and not next_has_label:
                amt = extract_amount_from_line(next_line)
        if amt is not None:
            out.append((i, amt))
    return out


def find_date(text: str):
    """Return ISO date 'YYYY-MM-DD' from text. Prefers dates near a 'Date' label."""
    # Combine of all dates found in text; label-adjacent dates get higher weight.
    date_patterns = [
        (r'\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b', 'dmy4'),
        (r'\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})\b', 'dmy2'),
        (r'\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b', 'ymd'),
        (r'\b(\d{1,2})[ \-]([A-Za-z]{3,9})[ \-](\d{2,4})\b', 'dMy'),
    ]
    results = []  # list of (date_iso, weight)
    for m_iter_pat, kind in date_patterns:
        for m in re.finditer(m_iter_pat, text):
            try:
                if kind == 'dmy4':
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif kind == 'dmy2':
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    y = 2000 + y if y < 70 else 1900 + y
                elif kind == 'ymd':
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    d = int(m.group(1))
                    mo = MONTHS.get(m.group(2)[:3].lower())
                    if mo is None:
                        continue
                    y = int(m.group(3))
                    if y < 100:
                        y = 2000 + y if y < 70 else 1900 + y
                if not (1 <= d <= 31 and 1 <= mo <= 12 and 2000 <= y <= 2099):
                    continue
                iso = f"{y:04d}-{mo:02d}-{d:02d}"
                # Weight: higher if the 50 chars preceding the match contain 'DATE'
                lead = text[max(0, m.start() - 60): m.start()].upper()
                weight = 3 if 'DATE' in lead else 1
                results.append((iso, weight, m.start()))
            except ValueError:
                continue
    if not results:
        return None
    # Pick highest total weight; break ties by earliest occurrence.
    totals = {}
    first_pos = {}
    for iso, w, pos in results:
        totals[iso] = totals.get(iso, 0) + w
        first_pos.setdefault(iso, pos)
    best = sorted(totals.items(), key=lambda kv: (-kv[1], first_pos[kv[0]]))
    return best[0][0]


def process(img_path: str):
    texts = ocr_variants(img_path)

    # Date: vote across variants, preferring label-adjacent dates per variant.
    date_votes = Counter()
    date_first_variant = {}
    for v_idx, t in enumerate(texts):
        d = find_date(t)
        if d:
            date_votes[d] += 1
            date_first_variant.setdefault(d, v_idx)
    if date_votes:
        max_v = max(date_votes.values())
        top = [d for d, c in date_votes.items() if c == max_v]
        top.sort(key=lambda d: date_first_variant[d])
        date = top[0]
    else:
        date = None

    # Amount: pick the highest-priority tier that has any candidate across
    # variants, then within that tier:
    #   1. If the raw-OCR variant (texts[0]) has candidates that all agree,
    #      trust that value - raw tesseract often reads thin fonts correctly
    #      even when upscaling introduces 5<->9 style errors.
    #   2. Otherwise, pick the mode of "last-candidate per variant"; break
    #      ties by overall candidate frequency across variants.
    amount = None
    for tier_idx in range(len(INCLUDE_TIERS)):
        per_variant = [tier_candidates(t, tier_idx) for t in texts]
        last_per_variant = [c[-1][1] for c in per_variant if c]
        all_candidates = [amt for cands in per_variant for _, amt in cands]
        if not last_per_variant:
            continue
        raw_cands = per_variant[0]
        # Trust raw OCR only when it provides two or more mutually-agreeing
        # candidates - a single raw candidate is not more reliable than
        # preprocessed variants.
        if len(raw_cands) >= 2 and len({amt for _, amt in raw_cands}) == 1:
            amount = raw_cands[0][1]
        else:
            c_last = Counter(last_per_variant)
            max_count = max(c_last.values())
            top = [v for v, c in c_last.items() if c == max_count]
            if len(top) == 1:
                amount = top[0]
            else:
                c_all = Counter(all_candidates)
                top.sort(key=lambda v: (-c_all[v], last_per_variant.index(v)))
                amount = top[0]
        break

    amount_str = f"{amount:.2f}" if amount is not None else None
    return date, amount_str


def main():
    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])

    for fn in sorted(os.listdir(IMG_DIR)):
        if not fn.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        path = os.path.join(IMG_DIR, fn)
        date, amt = process(path)
        ws.append([fn, date, amt])
        print(f"{fn}: date={date} amount={amt}")

    wb.save(OUT_XLSX)
    print(f"\nSaved {OUT_XLSX}")


if __name__ == "__main__":
    main()
