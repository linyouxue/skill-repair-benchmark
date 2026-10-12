import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from openpyxl import Workbook


IMG_DIR = Path('/app/workspace/dataset/img')
OUT_XLSX = Path('/app/workspace/stat_ocr.xlsx')


@dataclass(frozen=True)
class OcrLine:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float
    source: str


MONTHS = {
    'JAN': 1,
    'FEB': 2,
    'MAR': 3,
    'APR': 4,
    'MAY': 5,
    'JUN': 6,
    'JUL': 7,
    'AUG': 8,
    'SEP': 9,
    'SEPT': 9,
    'OCT': 10,
    'NOV': 11,
    'DEC': 12,
}


_DATE_LABEL_RE = re.compile(r"\b(?:DATE|DTE|DAT|DAT\.|QATE|OATE|DATS|QATES|OATES)\b", re.IGNORECASE)


def _resize_for_ocr(img: Image.Image) -> Image.Image:
    if img.mode != 'RGB':
        img = img.convert('RGB')

    w, h = img.size
    if min(w, h) < 1000:
        img = img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    return img


def _preprocess(img: Image.Image) -> Image.Image:
    img = _resize_for_ocr(img)

    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.SHARPEN)

    # Slightly increase contrast for faint scans
    gray = ImageEnhance.Contrast(gray).enhance(1.2)
    return gray


def _ocr_lines(img: Image.Image, *, psm: int, source: str) -> list[OcrLine]:
    data = pytesseract.image_to_data(
        img,
        output_type=pytesseract.Output.DICT,
        config=f'--oem 3 --psm {psm}',
    )

    n = len(data['text'])
    groups: dict[tuple[int, int, int], list[int]] = {}
    for i in range(n):
        if not data['text'][i].strip():
            continue
        key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        groups.setdefault(key, []).append(i)

    lines: list[OcrLine] = []
    for idxs in groups.values():
        words = [data['text'][i].strip() for i in idxs if data['text'][i].strip()]
        if not words:
            continue
        text = ' '.join(words)
        left = min(data['left'][i] for i in idxs)
        top = min(data['top'][i] for i in idxs)
        right = max(data['left'][i] + data['width'][i] for i in idxs)
        bottom = max(data['top'][i] + data['height'][i] for i in idxs)
        confs = [float(data['conf'][i]) for i in idxs if str(data['conf'][i]).strip() not in {'-1', ''}]
        conf = sum(confs) / len(confs) if confs else 0.0
        lines.append(OcrLine(text=text, left=left, top=top, width=right - left, height=bottom - top, conf=conf, source=source))

    lines.sort(key=lambda l: (l.top, l.left))
    return lines


_DATE_YMD_RE = re.compile(r'(?<!\d)(\d{4})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})(?!\d)')
_DATE_DMY_4_RE = re.compile(r'(?<!\d)(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{4})(?!\d)')
# 2-digit year date; block matches that are prefixes of a longer date (e.g. "19-18/01/2018")
_DATE_DMY_2_RE = re.compile(r'(?<!\d)(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{2})(?!\d)(?!\s*[-/]\s*\d)')
_DATE_DMY_COMPACT_RE = re.compile(r'(?<!\d)(\d{1,2})(\d{1,2})(\d{4})(?!\d)')
_DATE_YMD_COMPACT_RE = re.compile(r'(?<!\d)(\d{4})(\d{1,2})(\d{1,2})(?!\d)')
_DATE_MONTHNAME_RE = re.compile(
    r'(?<!\w)(\d{1,2})\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)[A-Z]*\s*(\d{2,4})(?!\w)',
    re.IGNORECASE,
)


def _year_to_4(y: int) -> int:
    if y < 100:
        return 2000 + y if y <= 79 else 1900 + y
    return y


def _valid_ymd(y: int, m: int, d: int) -> bool:
    if not (1900 <= y <= 2099 and 1 <= m <= 12 and 1 <= d <= 31):
        return False
    # Basic day bounds per month, with Feb leap check.
    if m in {4, 6, 9, 11} and d > 30:
        return False
    if m == 2:
        leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
        return d <= (29 if leap else 28)
    return True


def _parse_date_candidates(text: str) -> list[str]:
    t = text.strip()
    out: list[str] = []

    for m in _DATE_YMD_RE.finditer(t):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if _valid_ymd(y, mo, d):
            out.append(f'{y:04d}-{mo:02d}-{d:02d}')

    for m in _DATE_DMY_4_RE.finditer(t):
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        d, mo = a, b
        if a <= 12 < b:
            mo, d = a, b
        elif b <= 12 < a:
            d, mo = a, b
        if _valid_ymd(y, mo, d):
            out.append(f'{y:04d}-{mo:02d}-{d:02d}')

    for m in _DATE_DMY_2_RE.finditer(t):
        a, b, y = int(m.group(1)), int(m.group(2)), _year_to_4(int(m.group(3)))
        d, mo = a, b
        if a <= 12 < b:
            mo, d = a, b
        elif b <= 12 < a:
            d, mo = a, b
        if _valid_ymd(y, mo, d):
            out.append(f'{y:04d}-{mo:02d}-{d:02d}')

    for m in _DATE_MONTHNAME_RE.finditer(t):
        d = int(m.group(1))
        mo = MONTHS.get(m.group(2).upper())
        y = _year_to_4(int(m.group(3)))
        if mo and _valid_ymd(y, mo, d):
            out.append(f'{y:04d}-{mo:02d}-{d:02d}')

    # Compact forms without separators (handles e.g. 2032018 as 20 3 2018)
    compact = re.sub(r'[^0-9]', '', t)
    if 6 <= len(compact) <= 8:
        # Try year-at-end DMY with variable day/month width.
        if len(compact) in {7, 8}:
            y = int(compact[-4:])
            rest = compact[:-4]
            for split in (1, 2):
                if split >= len(rest):
                    continue
                d = int(rest[:split])
                mo = int(rest[split:])
                if _valid_ymd(y, mo, d):
                    out.append(f'{y:04d}-{mo:02d}-{d:02d}')
        for m in _DATE_DMY_COMPACT_RE.finditer(compact):
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if _valid_ymd(y, mo, d):
                out.append(f'{y:04d}-{mo:02d}-{d:02d}')
        for m in _DATE_YMD_COMPACT_RE.finditer(compact):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if _valid_ymd(y, mo, d):
                out.append(f'{y:04d}-{mo:02d}-{d:02d}')

    # De-duplicate while preserving order.
    seen = set()
    dedup: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            dedup.append(s)
    return dedup


_AMOUNT_RE = re.compile(r'(?<!\d)(?:RM|RN|R\$|\$)?\s*([0-9]{1,3}(?:[, ]?[0-9]{3})*(?:[\.,][0-9]{2,3})|[0-9]+(?:[\.,][0-9]{2,3}))(?!\d)')


def _normalize_numeric_context(s: str) -> str:
    s = s.replace('’', "'")
    s = re.sub(r'(\d)\s+([\.,]\d)', r'\1\2', s)
    s = re.sub(r'(?<=\d)[oO](?=\d)', '0', s)
    s = re.sub(r'(?<=\d)[uU](?=\d)', '0', s)
    s = re.sub(r'(?<=\d)[lI](?=\d)', '1', s)
    # Decimal comma (e.g. 73,40)
    s = re.sub(r'(?<=\d),(?=\d{2}(?!\d))', '.', s)
    return s


def _parse_amounts(text: str) -> list[Decimal]:
    t = _normalize_numeric_context(text)
    vals: list[Decimal] = []
    for m in _AMOUNT_RE.finditer(t):
        raw = m.group(1)
        raw = raw.replace(' ', '').replace(',', '')
        try:
            d = Decimal(raw)
        except InvalidOperation:
            continue
        # Receipts totals are typically 2 decimals; quantize if 3.
        d = d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if d >= 0:
            vals.append(d)
    return vals


_KEYWORD_SCORES: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r'\bGRAND\s+TOTAL\b', re.I), 120),
    (re.compile(r'\bTOTAL\s*[:]?\s*R[MN]\b', re.I), 110),
    (re.compile(r'\bTOTAL\s+AMOUNT\b', re.I), 105),
    (re.compile(r'\bROUNDED\s+TOTAL\b', re.I), 100),
    (re.compile(r'\bTOTAL\s+ROUNDED\b', re.I), 98),
    (re.compile(r'\bTOTAL\s+AFTER\s+(?:ADJ|ADJUST|ROUNDING)\b', re.I), 98),
    (re.compile(r'\bNETT\s+TOTAL\b', re.I), 95),
    (re.compile(r'\bNET\s+TOTAL\b', re.I), 93),
    (re.compile(r'\bTOTAL\s+DUE\b', re.I), 92),
    (re.compile(r'\bAMOUNT\s+DUE\b', re.I), 92),
    (re.compile(r'\bBALANCE\s+DUE\b', re.I), 92),
    (re.compile(r'\bTOTAL\b', re.I), 70),
]

_NONPAY_PENALTIES: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r'\bSUB\s*-?\s*TOTAL\b', re.I), 80),
    (re.compile(r'\bDISCOUNT\b', re.I), 40),
    (re.compile(r'\bCHANGE\b', re.I), 120),
    (re.compile(r'\bCASH\b', re.I), 50),
    (re.compile(r'\bTENDERED\b', re.I), 50),
    (re.compile(r'\bVISA\b', re.I), 70),
    (re.compile(r'\bMASTERCARD\b', re.I), 70),
    (re.compile(r'\bAMEX\b', re.I), 70),
    (re.compile(r'\bSUMMARY\b', re.I), 80),
    (re.compile(r'\bTAX\s+SUMMARY\b', re.I), 100),
    (re.compile(r'\bGST\s+SUMMARY\b', re.I), 100),
    (re.compile(r'\bTAX\s+CODE\b', re.I), 100),
]


def _score_total_line(line: OcrLine, img_h: int) -> int:
    t = line.text
    score = 0
    for pat, w in _KEYWORD_SCORES:
        if pat.search(t):
            score = max(score, w)

    up = t.upper()
    if 'ROUND' in up or 'AFTER ADJ' in up or 'AFTER' in up and 'ROUND' in up:
        score += 25

    # Favor values nearer the bottom of the receipt.
    y_frac = (line.top + line.height / 2) / max(img_h, 1)
    score += int(y_frac * 20)

    for pat, p in _NONPAY_PENALTIES:
        if pat.search(t):
            score -= p

    # Slightly favor higher-confidence OCR lines.
    score += int((line.conf or 0.0) / 20)

    return score


def _extract_total_amount(lines: list[OcrLine], img_h: int) -> str | None:
    scores_by_amt: dict[Decimal, list[int]] = {}
    after_round_amts: set[Decimal] = set()
    plain_total_amts: set[Decimal] = set()
    rounding_adjs: list[Decimal] = []

    def add_score(amt: Decimal, score: int) -> None:
        scores_by_amt.setdefault(amt, []).append(score)

    def is_numericish(text: str) -> bool:
        if len(re.findall(r'[A-Za-z]', text)) > 1:
            return False
        return bool(_parse_amounts(text))

    for i, ln in enumerate(lines):
        base = _score_total_line(ln, img_h)
        up = ln.text.upper()
        if 'INCL' in up or 'INCLUSIVE' in up:
            base += 8

        amounts = _parse_amounts(ln.text)
        if amounts:
            if re.search(r'\b(?:ROUNDED\s+TOTAL|TOTAL\s+ROUNDED|TOTAL\s+AFTER|AFTER\s+ROUND)\b', up):
                after_round_amts.update(amounts)
            if 'ROUND' in up and 'TOTAL' not in up:
                rounding_adjs.extend([a for a in amounts if a < Decimal('1.00')])
            if 'TOTAL' in up and 'AFTER' not in up and 'ROUND' not in up and not re.search(r'\bSUB\b', up):
                plain_total_amts.update(amounts)

            for amt in amounts[-2:]:
                s = base
                if re.search(rf'{re.escape(str(amt))}\s*$', _normalize_numeric_context(ln.text)):
                    s += 5
                add_score(amt, s)

            # For strong total-label lines, also look for a nearby numeric-only value.
            if base >= 90:
                for j in range(max(0, i - 3), min(len(lines), i + 4)):
                    if j == i:
                        continue
                    other = lines[j]
                    if abs(other.top - ln.top) > max(ln.height, other.height):
                        continue
                    if other.left < ln.left + int(ln.width * 0.25):
                        continue
                    if re.search(r'\b(CASH|CHANGE|DISCOUNT|GST|TAX|SUB)\b', other.text, re.I):
                        continue
                    if not is_numericish(other.text):
                        continue
                    other_amts = _parse_amounts(other.text)
                    if other_amts:
                        add_score(other_amts[-1], base - 2)

            continue

        # Label-only line: look at next line for a standalone amount.
        if base < 85 or i + 1 >= len(lines):
            continue
        nxt = lines[i + 1]
        if nxt.top - ln.top > max(ln.height * 3, 80):
            continue
        nxt_amounts = _parse_amounts(nxt.text)
        if not nxt_amounts:
            continue
        if re.search(r'\b(CASH|CHANGE|SUB\s*-?\s*TOTAL|DISCOUNT|GST|TAX|ROUND)\b', nxt.text, re.I):
            continue
        add_score(nxt_amounts[-1], base - 5)

    # Rounding-consistency adjustment: when rounding is small, prefer totals consistent with it.
    if rounding_adjs and plain_total_amts:
        r = min(rounding_adjs)
        for amt in list(scores_by_amt.keys()):
            diff = min(abs(amt - t) for t in plain_total_amts)
            if diff <= max(Decimal('0.20'), r + Decimal('0.05')):
                add_score(amt, 80)
            elif amt in after_round_amts and r <= Decimal('0.50') and diff > Decimal('1.00'):
                add_score(amt, -200)

    if not scores_by_amt:
        return None

    best_amt: Decimal | None = None
    best_agg: int | None = None
    best_single: int | None = None
    for amt, scores in scores_by_amt.items():
        top_scores = sorted(scores, reverse=True)[:3]
        agg = sum(top_scores)
        single = top_scores[0]
        if best_agg is None or agg > best_agg or (agg == best_agg and single > (best_single or -10**9)):
            best_amt = amt
            best_agg = agg
            best_single = single

    return f'{best_amt:.2f}' if best_amt is not None else None


def _extract_date(lines: list[OcrLine], img_h: int) -> str | None:
    scores_by_date: dict[str, list[int]] = {}

    def add_score(ds: str, score: int) -> None:
        scores_by_date.setdefault(ds, []).append(score)

    for ln in lines:
        up = ln.text.upper()
        if 'GST ACT' in up or ('SECTION' in up and 'GST' in up) or ('ACT' in up and 'GST' in up):
            continue

        cands = _parse_date_candidates(ln.text)
        if not cands:
            continue

        y_frac = (ln.top + ln.height / 2) / max(img_h, 1)
        base = int((ln.conf or 0.0) / 15)
        if _DATE_LABEL_RE.search(up):
            base += 20
        if 'TIME' in up or 'ORD' in up or 'INV' in up or 'RECEIPT' in up:
            base += 5
        base += int((1 - min(y_frac, 1.0)) * 6)

        for ds in cands:
            score = base
            if ds.startswith('20'):
                score += 4
            add_score(ds, score)

    if not scores_by_date:
        return None

    best_ds: str | None = None
    best_agg: int | None = None
    best_single: int | None = None
    for ds, scores in scores_by_date.items():
        top_scores = sorted(scores, reverse=True)[:3]
        agg = sum(top_scores)
        single = top_scores[0]
        if best_agg is None or agg > best_agg or (agg == best_agg and single > (best_single or -10**9)):
            best_ds = ds
            best_agg = agg
            best_single = single

    return best_ds


def extract_fields(image_path: Path) -> tuple[str | None, str | None]:
    img = Image.open(image_path)

    raw = _resize_for_ocr(img)
    pre = _preprocess(img)

    lines: list[OcrLine] = []
    lines.extend(_ocr_lines(raw, psm=6, source='raw_psm6'))
    lines.extend(_ocr_lines(raw, psm=11, source='raw_psm11'))
    lines.extend(_ocr_lines(pre, psm=6, source='pre_psm6'))
    lines.extend(_ocr_lines(pre, psm=11, source='pre_psm11'))

    # De-dup very similar lines.
    seen = set()
    uniq: list[OcrLine] = []
    for ln in sorted(lines, key=lambda l: (l.top, l.left, -l.conf)):
        key = (re.sub(r'\s+', ' ', ln.text.strip().upper()), ln.top // 5)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(ln)

    img_h = raw.size[1]
    date = _extract_date(uniq, img_h)
    total = _extract_total_amount(uniq, img_h)
    return date, total


def write_xlsx(rows: list[tuple[str, str | None, str | None]]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = 'results'

    ws.append(['filename', 'date', 'total_amount'])
    for fn, date, total in rows:
        ws.append([fn, date, total])

    # Ensure only one sheet exists.
    for name in list(wb.sheetnames):
        if name != 'results':
            wb.remove(wb[name])

    wb.save(OUT_XLSX)


def main() -> None:
    image_paths = sorted([p for p in IMG_DIR.iterdir() if p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}])
    rows: list[tuple[str, str | None, str | None]] = []

    for p in image_paths:
        date, total = extract_fields(p)
        rows.append((p.name, date, total))

    write_xlsx(rows)


if __name__ == '__main__':
    main()
