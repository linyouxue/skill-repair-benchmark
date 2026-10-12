import os
import re
import json
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from openpyxl import Workbook

IMG_DIR = "/app/workspace/dataset/img"
OUT_XLSX = "/app/workspace/stat_ocr.xlsx"

EXCLUSION = ["SUBTOTAL", "SUB TOTAL", "TAX", "GST", "SST",
             "DISCOUNT", "CHANGE", "CASH TENDERED",
             # Common OCR misreads of GST (used only to broaden exclusion)
             "GS1", "GSI"]

# Priority groups
PRIO_GROUPS = [
    ["GRAND TOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    ["TOTAL", "AMOUNT", "TOTAL DUE", "AMOUNT DUE",
     "BALANCE DUE", "NETT TOTAL", "NET TOTAL"],
]

MONEY_RE = re.compile(r'(?<![\d.,])\d{1,3}(?:,\d{3})*\.\d{2}(?![\d])|(?<![\d.,])\d+\.\d{2}(?![\d])')
# Loose money pattern that accepts space or colon in place of decimal (OCR errors)
LOOSE_MONEY_RE = re.compile(r'(?<![\d.,:])(\d{1,3}(?:,\d{3})*|\d+)[\s:](\d{2})(?![\d])')


def ocr_image(path):
    img = Image.open(path)
    gray = ImageOps.grayscale(img)
    w, h = img.size
    scaled3 = img.resize((w*3, h*3), Image.LANCZOS).convert('L')
    variants = [
        ("orig", img),
        ("gray_ac", ImageOps.autocontrast(gray)),
        ("sharp", ImageOps.autocontrast(gray).filter(ImageFilter.SHARPEN)),
        ("3x_ac", ImageOps.autocontrast(scaled3)),
        ("3x_th140", scaled3.point(lambda p: 255 if p > 140 else 0)),
        ("3x_th160", scaled3.point(lambda p: 255 if p > 160 else 0)),
    ]
    psm_modes = ["--psm 6", "--psm 4", "--psm 11"]
    results = []
    for name, vimg in variants:
        for psm in psm_modes:
            try:
                text = pytesseract.image_to_string(vimg, config=psm)
                if text.strip():
                    results.append((name, psm, text))
            except Exception:
                pass
    return results


def parse_money(tok):
    tok = tok.replace(',', '').strip()
    try:
        val = float(tok)
        return f"{val:.2f}"
    except Exception:
        return None


def find_total_from_text(text):
    """Try to find total amount using priority groups, with fallback to next-line."""
    lines = [l.rstrip() for l in text.splitlines()]
    for group in PRIO_GROUPS:
        # First pass: prefer same-line money match on any keyword hit
        fallback_candidates = []
        same_line_hit = None
        for i, line in enumerate(lines):
            up = line.upper()
            if any(ex in up for ex in EXCLUSION):
                continue
            if not any(kw in up for kw in group):
                continue
            moneys = MONEY_RE.findall(line)
            if not moneys:
                # Try loose money (space/colon as decimal separator) on the keyword line
                lm = LOOSE_MONEY_RE.findall(line)
                if lm:
                    whole, cents = lm[-1]
                    moneys = [f"{whole}.{cents}"]
            if moneys:
                if same_line_hit is None:
                    same_line_hit = parse_money(moneys[-1])
            else:
                # Fallback: next non-empty line's last money
                for j in range(i+1, min(i+3, len(lines))):
                    nxt = lines[j]
                    if not nxt.strip():
                        continue
                    nup = nxt.upper()
                    if any(ex in nup for ex in EXCLUSION):
                        break
                    nmoneys = MONEY_RE.findall(nxt)
                    if nmoneys:
                        fallback_candidates.append(parse_money(nmoneys[-1]))
                        break
                    nums = re.findall(r'\d[\d,]*\.?\d*', nxt)
                    if nums and '.' in nums[-1]:
                        fallback_candidates.append(parse_money(nums[-1]))
                    break
        if same_line_hit is not None:
            return same_line_hit
        if fallback_candidates:
            return fallback_candidates[0]
    return None


DATE_PATTERNS = [
    # DD-MM-YYYY, DD/MM/YYYY
    (re.compile(r'(\b\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b'), "dmy"),
    # YYYY-MM-DD
    (re.compile(r'\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b'), "ymd"),
    # DD MMM YYYY
    (re.compile(r'\b(\d{1,2})[\s\-]+([A-Za-z]{3,9})[\s\-,]+(\d{2,4})\b'), "dmy_text"),
    # MMM DD, YYYY
    (re.compile(r'\b([A-Za-z]{3,9})[\s\-]+(\d{1,2})[\s\-,]+(\d{2,4})\b'), "mdy_text"),
]

MONTHS = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,'july':7,
    'august':8,'september':9,'october':10,'november':11,'december':12,
}


def normalize_year(y):
    y = int(y)
    if y < 100:
        y = 2000 + y if y < 70 else 1900 + y
    return y


def _try_parse_date(m, kind):
    try:
        if kind == "dmy":
            d, mo, y = int(m.group(1)), int(m.group(2)), normalize_year(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2099:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        elif kind == "ymd":
            y, mo, d = normalize_year(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2099:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        elif kind == "dmy_text":
            d = int(m.group(1)); mon = MONTHS.get(m.group(2).lower())
            y = normalize_year(m.group(3))
            if mon and 1 <= d <= 31 and 1900 <= y <= 2099:
                return f"{y:04d}-{mon:02d}-{d:02d}"
        elif kind == "mdy_text":
            mon = MONTHS.get(m.group(1).lower())
            d = int(m.group(2)); y = normalize_year(m.group(3))
            if mon and 1 <= d <= 31 and 1900 <= y <= 2099:
                return f"{y:04d}-{mon:02d}-{d:02d}"
    except Exception:
        pass
    return None


def find_date_candidates(text, labeled_only=False):
    """Return list of candidate ISO dates found in text.
    If labeled_only=True, only consider dates on lines containing 'DATE'."""
    out = []
    for line in text.splitlines():
        if labeled_only and "DATE" not in line.upper() and "DATA" not in line.upper():
            # 'DATA' due to OCR confusing 'Date' with 'Data'
            continue
        for pat, kind in DATE_PATTERNS:
            for m in pat.finditer(line):
                d = _try_parse_date(m, kind)
                if d:
                    out.append(d)
    return out


def find_date_from_text(text):
    cands = find_date_candidates(text)
    return cands[0] if cands else None


def extract_from_image(path):
    from collections import Counter
    results = ocr_image(path)
    total = None
    date = None
    all_text = "\n".join(r[2] for r in results)

    total_candidates = []
    date_labeled = []
    date_any = []
    for name, psm, text in results:
        t = find_total_from_text(text)
        if t:
            total_candidates.append(t)
        date_labeled.extend(find_date_candidates(text, labeled_only=True))
        date_any.extend(find_date_candidates(text, labeled_only=False))

    if total_candidates:
        total = Counter(total_candidates).most_common(1)[0][0]

    def pick_date(cands):
        if not cands:
            return None
        # Vote by (month, day) first (year is often misread when day/month aren't)
        md_counts = Counter((c[5:7], c[8:10]) for c in cands)
        top_md, _ = md_counts.most_common(1)[0]
        # Among candidates matching this md, pick most common year
        year_counts = Counter(c[:4] for c in cands if (c[5:7], c[8:10]) == top_md)
        top_year, _ = year_counts.most_common(1)[0]
        return f"{top_year}-{top_md[0]}-{top_md[1]}"

    date = pick_date(date_labeled) or pick_date(date_any)

    return date, total, all_text


def main():
    files = sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith('.jpg'))
    rows = []
    for f in files:
        path = os.path.join(IMG_DIR, f)
        date, total, _ = extract_from_image(path)
        print(f"{f}: date={date}, total={total}")
        rows.append((f, date, total))

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for f, d, t in rows:
        ws.append([f, d, t])
    wb.save(OUT_XLSX)
    print(f"Saved {OUT_XLSX}")


if __name__ == "__main__":
    main()
