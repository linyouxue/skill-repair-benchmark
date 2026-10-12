import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytesseract
from PIL import Image, ImageFilter, ImageOps
from openpyxl import Workbook

IMG_DIR = Path('/app/workspace/dataset/img')
OUT_XLSX = Path('/app/workspace/stat_ocr.xlsx')

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff'}

TOTAL_LABEL_PATTERNS = [
    (100, re.compile(r"\bGRAND\s+TOTAL\b", re.I)),
    (92, re.compile(r"\bTOTAL\s*(?:[:\-])?\s*(?:R\s*M|RM)\b", re.I)),
    (90, re.compile(r"\bTOTAL\s*(?:[:\-])?\s*(?:R\s*N|RN)\b", re.I)),
    (88, re.compile(r"\bTOTAL\s*[:\-]\s*(?:R\s*M|RM|R\s*N|RN)\b", re.I)),
    (87, re.compile(r"^TOTAL\s*[:\-]", re.I)),

    (85, re.compile(r"\bTOTAL\s+AMOUNT\b", re.I)),
    (84, re.compile(r"\bTOTAL\s+DUE\b", re.I)),
    (84, re.compile(r"\bAMOUNT\s+DUE\b", re.I)),
    (83, re.compile(r"\bBALANCE\s+DUE\b", re.I)),
    (83, re.compile(r"\bNETT\s+TOTAL\b", re.I)),
    (83, re.compile(r"\bNET\s+TOTAL\b", re.I)),
    (82, re.compile(r"\bTOTAL\b.*\bAFTER\b.*\bADJ\b", re.I)),
    (80, re.compile(r"\bTOTAL\b.*\bINCL(?:USIVE)?\b.*\bGST\b", re.I)),
    (78, re.compile(r"\bTOTAL\s+SALES\b", re.I)),
    (70, re.compile(r"\bTOTAL\b", re.I)),
]

NON_PAYABLE_CUES = [
    re.compile(r"\bSUB\s*TOTAL\b", re.I),
    re.compile(r"\bSUBTOTAL\b", re.I),
    re.compile(r"\bDISCOUNT\b", re.I),
    re.compile(r"\bCHANGE\b", re.I),
    re.compile(r"\bCASH\s*TENDERED\b", re.I),
    re.compile(r"\bSERV\.?\s*CHARGE\b", re.I),
]

SKIP_CONTEXT = [
    re.compile(r'\bGST\s+SUMMARY\b', re.I),
    re.compile(r'\bTAX\s+SUMMARY\b', re.I),
    re.compile(r'\bAMOUNT\s+TAX\b', re.I),
]

SUMMARY_SECTION_HEADERS = [
    re.compile(r"\bGST\s+SUMMARY\b", re.I),
    re.compile(r"\bTAX\s+SUMMARY\b", re.I),
]

ITEM_COUNT_CUES = [
    re.compile(r"\bITEM\b", re.I),
    re.compile(r"\bITEM\s*COUNT\b", re.I),
    re.compile(r"\bPAX\b", re.I),
    re.compile(r"\bTEM\(S\)\b", re.I),
    re.compile(r"\bTOTAL\s+ITEM", re.I),
]

PASS_BONUS = {
    'base_psm6': 22,
    'base_psm4': 18,
    'sharp_psm6': 18,
    'sharp_psm4': 14,
    'up_psm6': 10,
    'up_psm4': 8,
    'thr_psm6': 4,
    'inv_psm6': 0,
}



DATE_CONTEXT_BONUS = [
    (25, re.compile(r'\bDATE\b', re.I)),
    (20, re.compile(r'\bINVOICE\b', re.I)),
    (15, re.compile(r'\bTIME\b', re.I)),
    (15, re.compile(r'\bRECEIPT\b', re.I)),
]

@dataclass
class OcrPass:
    name: str
    psm: int
    image: Image.Image


def iter_images_sorted(img_dir: Path):
    files = [p for p in img_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    return sorted(files, key=lambda p: p.name)


def make_ocr_passes(img: Image.Image):
    base = ImageOps.grayscale(img)
    base = ImageOps.autocontrast(base)
    sharp = base.filter(ImageFilter.SHARPEN)

    scale = 2
    up = sharp.resize((sharp.width * scale, sharp.height * scale), Image.Resampling.LANCZOS)
    thr = up.point(lambda p: 255 if p > 170 else 0)
    inv = ImageOps.autocontrast(ImageOps.invert(up))

    return [
        OcrPass('base_psm6', 6, base),
        OcrPass('base_psm4', 4, base),
        OcrPass('sharp_psm6', 6, sharp),
        OcrPass('sharp_psm4', 4, sharp),
        OcrPass('up_psm6', 6, up),
        OcrPass('up_psm4', 4, up),
        OcrPass('thr_psm6', 6, thr),
        OcrPass('inv_psm6', 6, inv),
    ]


def ocr_lines(pass_: OcrPass):
    config = f'--oem 3 --psm {pass_.psm}'
    text = pytesseract.image_to_string(pass_.image, config=config)
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


_money_re = re.compile(r'(?<!\d)(\d{1,3}(?:,\d{3})+(?:[\.,]\d{2})|\d+(?:[\.,]\d{2})|\d+)(?!\d)')


def _normalize_amount_token(tok: str):
    t = re.sub(r'[^0-9,\.]', '', tok.strip())
    if not t:
        return None

    if ',' in t and '.' not in t:
        parts = t.split(',')
        if len(parts) == 2 and len(parts[1]) == 2:
            t = parts[0] + '.' + parts[1]
        else:
            t = t.replace(',', '')
    elif ',' in t and '.' in t:
        t = t.replace(',', '')

    if t.count('.') > 1:
        last = t.rfind('.')
        t = t[:last].replace('.', '') + t[last:]

    if '.' in t:
        a, b = t.split('.', 1)
        b = re.sub(r'[^0-9]', '', b)
        if len(b) == 0:
            b = '00'
        elif len(b) == 1:
            b = b + '0'
        else:
            b = b[:2]
        a = a.lstrip('0') or '0'
        return f"{a}.{b}"

    a = t.lstrip('0') or '0'
    return f"{a}.00"


def _best_amount_from_text(text: str):
    cleaned = re.sub(r"(\d+)\s*[\.,]\s*(\d{2})(?!\d)", r"\1.\2", text)
    cleaned = re.sub(r"(?<!\d)(\d{1,5})\s+(\d{2})(?!\d)", r"\1.\2", cleaned)
    toks = _money_re.findall(cleaned)
    if not toks:
        return None

    dec_amts = []
    int_amts = []
    for t in toks:
        amt = _normalize_amount_token(t)
        if amt is None:
            continue
        if '.' in t or ',' in t:
            dec_amts.append(amt)
        else:
            int_amts.append(amt)

    if dec_amts:
        return dec_amts[-1]

    # integers only: choose the largest
    best = None
    best_val = None
    for a in int_amts:
        try:
            v = float(a)
        except Exception:
            continue
        if best_val is None or v > best_val:
            best_val = v
            best = a
    return best


def extract_amount_candidates(lines):
    cands = []
    skip_for = 0

    for i, line in enumerate(lines):
        norm = re.sub(r"\s+", " ", line).strip()

        if skip_for > 0:
            skip_for -= 1
            continue

        if any(p.search(norm) for p in SUMMARY_SECTION_HEADERS):
            skip_for = 6
            continue

        if any(p.search(norm) for p in SKIP_CONTEXT):
            continue

        label_score = 0
        for score, pat in TOTAL_LABEL_PATTERNS:
            if pat.search(norm):
                label_score = score
                break
        if label_score == 0:
            continue

        # ignore obvious item-count lines that contain TOTAL
        if label_score <= 70 and any(p.search(norm) for p in ITEM_COUNT_CUES):
            continue

        non_payable_penalty = 0
        if label_score <= 70 and any(p.search(norm) for p in NON_PAYABLE_CUES):
            non_payable_penalty = 25

        if re.search(r"\bGST\b", norm, re.I) and not re.search(r"\bINCL(?:USIVE)?\b", norm, re.I):
            non_payable_penalty += 60
        if re.search(r"\bTAX\b", norm, re.I) and re.search(r"\d\s*%", norm):
            non_payable_penalty += 40


        amt = _best_amount_from_text(norm)
        if amt is not None:
            cands.append((label_score - non_payable_penalty, float(i), amt, norm))
            continue

        # only associate next-line amount for strong labels
        if label_score >= 83 and i + 1 < len(lines):
            nxt = re.sub(r"\s+", " ", lines[i + 1]).strip()
            if any(p.search(nxt) for p in SUMMARY_SECTION_HEADERS) or any(p.search(nxt) for p in SKIP_CONTEXT):
                continue
            nxt_amt = _best_amount_from_text(nxt)
            if nxt_amt is not None:
                cands.append((label_score - non_payable_penalty - 8, i + 0.5, nxt_amt, norm + ' | ' + nxt))

    return cands


def choose_best_amount(all_lines_by_pass):
    cands = []
    for pass_name, lines in all_lines_by_pass.items():
        pass_bonus = PASS_BONUS.get(pass_name, 0)
        for score, idx, amt, ctx in extract_amount_candidates(lines):
            bonus = pass_bonus
            if re.search(r"\b(R\s*M|RM|R\s*N|RN)\b", ctx, re.I):
                bonus += 3
            if re.search(r"\bVISA\b|\bMASTER\b|\bAMEX\b", ctx, re.I):
                bonus -= 10
            if re.search(r"\d\s*[\.,]\s*\d{2}", ctx):
                bonus += 4
            cands.append((score + bonus, idx, amt, pass_name, ctx))

    if not cands:
        return None

    cands.sort(key=lambda x: (x[0], x[1]), reverse=True)

    groups = {}
    for cand in cands:
        amt = cand[2]
        g = groups.get(amt)
        if g is None:
            groups[amt] = {'count': 1, 'best': cand}
        else:
            g['count'] += 1
            if cand[0] > g['best'][0]:
                g['best'] = cand

    multi = [g for g in groups.values() if g['count'] >= 2]
    if multi:
        multi.sort(key=lambda g: (g['best'][0] + g['count'], g['best'][0], g['count']), reverse=True)
        best = multi[0]['best']
    else:
        best = cands[0]

    best_val = float(best[2])

    # avoid tiny values that often come from mis-association (e.g., item counts)
    for cand in cands[1:12]:
        if best_val < 2.0 and best[0] - cand[0] <= 10 and float(cand[2]) >= 2.0:
            best = cand
            best_val = float(cand[2])
            break

    # avoid extreme outliers (usually a spurious leading digit) when a close-scoring
    # smaller alternative exists; only apply to very large best values.
    if best_val >= 500.0:
        for cand in cands[1:12]:
            if best[0] - cand[0] <= 10:
                v = float(cand[2])
                if best_val >= 4.0 * v and v >= 1.0:
                    best = cand
                    best_val = v
                    break

    return best[2]


_date_patterns = [
    re.compile(r"(?<!\d)(20\d{2})\s*[\-/.]\s*(\d{1,2})\s*[\-/.]\s*(\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{1,2})\s*[\-/.]\s*(\d{1,2})\s*[\-/.]\s*(20\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{1,2})\s*[\-/.]\s*(\d{1,2})\s*[\-/.]\s*(\d{2})(?!\d)"),
]


def _normalize_year(yy: int):
    return yy if yy >= 100 else (2000 + yy if yy <= 69 else 1900 + yy)


def _component_variants(x: int, max_v: int):
    out = []
    if 1 <= x <= max_v:
        out.append(x)
        return out
    if 80 <= x <= 99:
        for v in (x - 80, x % 10):
            if 1 <= v <= max_v and v not in out:
                out.append(v)
    if 70 <= x <= 79:
        v = x - 70
        if 1 <= v <= max_v and v not in out:
            out.append(v)
    return out


def extract_date_candidates(lines):
    cands = []
    for i, line in enumerate(lines):
        norm = re.sub(r"\s+", " ", line).strip()
        for pat_i, pat in enumerate(_date_patterns):
            for m in pat.finditer(norm):
                bonus = 0
                for b, p in DATE_CONTEXT_BONUS:
                    if p.search(norm):
                        bonus += b

                if pat_i == 0:
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif pat_i == 1:
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    d, mo, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    y = _normalize_year(yy)

                candidates = []
                candidates.append((d, mo, 0))
                if d <= 12:
                    candidates.append((mo, d, -10))

                for mo2 in _component_variants(mo, 12):
                    candidates.append((d, mo2, -12))
                    if d <= 12:
                        candidates.append((mo2, d, -18))

                picked = None
                for dd, mm, pen in candidates:
                    try:
                        picked = date(y, mm, dd)
                        bonus += pen
                        break
                    except ValueError:
                        continue

                if picked is None:
                    continue

                score = 50 + bonus
                cands.append((score, -i, picked.isoformat(), norm))

    return cands


def choose_best_date(all_lines_by_pass):
    cands = []
    for pass_name, lines in all_lines_by_pass.items():
        pass_bonus = PASS_BONUS.get(pass_name, 0)
        for score, idx, iso, ctx in extract_date_candidates(lines):
            cands.append((score + pass_bonus, idx, iso))

    if not cands:
        return None

    cands.sort(reverse=True)
    return cands[0][2]


def extract_fields_from_image(img_path: Path):
    img = Image.open(img_path)
    all_lines_by_pass = {p.name: ocr_lines(p) for p in make_ocr_passes(img)}
    return choose_best_date(all_lines_by_pass), choose_best_amount(all_lines_by_pass)


def write_xlsx(rows, out_path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'results'

    ws.append(['filename', 'date', 'total_amount'])
    for r in rows:
        ws.append([r['filename'], r['date'], r['total_amount']])

    for name in list(wb.sheetnames):
        if name != 'results':
            del wb[name]

    wb.save(out_path)


def main():
    rows = []
    for p in iter_images_sorted(IMG_DIR):
        dt, amt = extract_fields_from_image(p)
        rows.append({'filename': p.name, 'date': dt, 'total_amount': amt})

    write_xlsx(rows, OUT_XLSX)


if __name__ == '__main__':
    main()
