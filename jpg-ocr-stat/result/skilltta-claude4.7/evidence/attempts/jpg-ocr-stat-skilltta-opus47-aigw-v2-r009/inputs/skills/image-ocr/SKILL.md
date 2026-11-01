---
name: image-ocr
description: Extract text content from images using Tesseract OCR via Python, including structured field extraction from receipts/forms with keyword-priority, rounding-aware totals, locale-aware dates, cross-anchor sanity checks, and strict null semantics
---

# Image OCR Skill

## Purpose
Extract text from images (JPG/PNG/WEBP/etc.) using Tesseract via `pytesseract`, and extract structured fields (dates, monetary totals) from receipts/invoices with rules that are robust to common OCR errors and to variations in receipt layout.

## When to Use
- Scanned documents, screenshots, photos of text, receipts, forms.
- Batch OCR into tabular outputs (CSV/Excel) with strict schemas and nullable fields.
- Structured extraction of date and total amount where accuracy depends on keyword priority, exclusions, cross-anchor validation, and locale-aware date parsing.

## Required Libraries

```python
import pytesseract
from PIL import Image, ImageOps, ImageFilter
import re, os
from datetime import datetime
from pathlib import Path
```

## Basic OCR Extraction

```python
def extract_text_from_image(image_path):
    img = Image.open(image_path)
    return pytesseract.image_to_string(img).strip()
```

## Preprocessing for Receipts / Low-Quality Scans

```python
def preprocess_for_receipt(image_path):
    img = Image.open(image_path).convert('L')
    img = ImageOps.autocontrast(img)
    w, h = img.size
    if max(w, h) < 1500:
        img = img.resize((w*2, h*2), Image.LANCZOS)
    return img
```

For faint/dense receipts also try a 3x upscale and/or `ImageFilter.SHARPEN`, plus a binarized variant when results are empty.

## Multi-Pass OCR (per-pass extraction, then arbitrate)

Do NOT concatenate OCR outputs across variants and run extraction on the blob — that creates spurious cross-line matches. Run OCR on multiple variants, run extraction PER PASS, then arbitrate.

```python
def ocr_variants(image_path):
    img = Image.open(image_path)
    gray = ImageOps.autocontrast(img.convert('L'))
    big = gray.resize((gray.width*2, gray.height*2), Image.LANCZOS) if max(gray.size) < 1500 else gray
    big3 = gray.resize((gray.width*3, gray.height*3), Image.LANCZOS) if max(gray.size) < 1200 else big
    variants = [
        (gray, '--psm 6'),
        (big, '--psm 6'),
        (big, '--psm 4'),
        (big3, '--psm 4'),
    ]
    outs = []
    for v, cfg in variants:
        try:
            outs.append(pytesseract.image_to_string(v, config=cfg))
        except Exception:
            pass
    return outs
```

## Structured Field Extraction from Receipts

### Keyword priority tiers (highest to lowest)

1. `GRAND TOTAL`
2. `TOTAL ROUNDED`, `ROUNDED TOTAL`, `TOTAL AFTER ROUNDING`, `TOTAL AMT ROUNDED`, `NET TOTAL`, `NETT TOTAL`
3. `TOTAL RM`, `TOTAL: RM`, `TOTAL (RM)`, `TOTAL RM INCLUDING GST`, `TOTAL RM INCL GST`
4. `TOTAL AMOUNT`, `AMOUNT DUE`, `BALANCE DUE`, `TOTAL DUE`, `TOTAL INCLUSIVE GST`, `TOTAL INCL GST`, `TOTAL INCLUDING GST`, `TOTAL INCL. OF GST`
5. Generic `TOTAL`, `AMOUNT`, including `TOTAL (INCLUSIVE OF GST)` / `TOTAL INCL. GST` / `TOTAL SALES INCL GST`

### Keyword matching tolerance

Before matching, normalise the line: uppercase, collapse whitespace, strip trailing punctuation. Then also test a `nospace` form (remove all spaces) against each keyword's nospace form. This recovers OCR corruptions like `GRANDTOTAL`, `TOTALRM`, `GRANDTOTA.` (truncated — see `tier_match` below for stem matching).

### Exclusion keywords (checked BEFORE any tier match on the same line)

Always skip lines whose semantic label is one of:
`SUBTOTAL`, `SUB TOTAL`, `SUB-TOTAL`, `TAX`, `GST`, `SST`, `DISCOUNT`, `CHANGE`, `CHANGE DUE`, `CASH TENDERED`, `CASH RECEIVED`, `CASH PAYMENT`, `PAYMENT`, `TENDER`, `TENDERED`, `VISA`, `MASTERCARD`, `MASTER CARD`, `DEBIT`, `CREDIT CARD`, `CARD`, `POINTS`, `LOYALTY`, `TOTAL ITEM(S)`, `TOTAL QTY`, `ITEM COUNT`, `TOTAL SAVINGS`, `AVERAGE / PAX`, `TAX TOTAL`, `GST SUMMARY`, `TAX SUMMARY`, `SERVICE CHARGE`, `SERV. CHARGE`, `ROUNDING ADJ`, `ROUNDING ADJUSTMENT`.

Note: `ROUNDED TOTAL` / `TOTAL ROUNDED` / `TOTAL AFTER ROUNDING` are NOT exclusions — they are high-priority tiers. `AMT EXCL GST`, `AMT. EXCL. GST`, `AMOUNT EXCL GST`, `TOTAL EXCL GST`, `TOTAL EXCLUDING GST` are exclusions (they are pre-tax amounts).

### Qualifier-downgrade keywords (not full exclusion)

Lines containing these are matched but ranked AFTER a cleaner plain-keyword line in the same tier:
`INCLUSIVE OF GST`, `INCL GST`, `INCL. GST`, `INCLUDING GST`, `BEFORE ROUNDING`, `GROSS`, `TOTAL SALES INCL`.

### Number regex and normalization

Monetary totals should match with exactly two decimals; accept looser forms only as a last-resort fallback.

```python
NUM_STRICT = re.compile(r'(?<![\d.,])(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})(?![\d])')
NUM_LOOSE  = re.compile(r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+)')

def normalize_amount_token(tok):
    t = tok.strip().replace(',', '').lstrip('-')
    t = re.sub(r'(?<=\d):(?=\d{2}\b)', '.', t)
    try:
        return float(t)
    except ValueError:
        return None

def last_strict_number(line):
    nums = NUM_STRICT.findall(line)
    if not nums:
        return None
    return normalize_amount_token(nums[-1])

def last_loose_number(line):
    nums = NUM_LOOSE.findall(line)
    for raw in reversed(nums):
        v = normalize_amount_token(raw)
        if v is not None:
            return v
    return None
```

### Total extraction algorithm (per OCR pass)

```python
TIERS = [
    ['GRAND TOTAL'],
    ['TOTAL ROUNDED', 'ROUNDED TOTAL', 'TOTAL AFTER ROUNDING', 'TOTAL AMT ROUNDED', 'NET TOTAL', 'NETT TOTAL'],
    ['TOTAL RM', 'TOTAL: RM', 'TOTAL (RM)'],
    ['TOTAL AMOUNT', 'AMOUNT DUE', 'BALANCE DUE', 'TOTAL DUE'],
    ['TOTAL', 'AMOUNT'],
]

EXCLUSIONS = [
    'SUBTOTAL','SUB TOTAL','SUB-TOTAL','TAX','GST','SST','DISCOUNT',
    'CHANGE','CHANGE DUE','CASH TENDERED','CASH RECEIVED','CASH PAYMENT',
    'PAYMENT','TENDER','TENDERED','VISA','MASTERCARD','MASTER CARD',
    'DEBIT','CREDIT CARD','CARD','POINTS','LOYALTY',
    'TOTAL ITEM(S)','TOTAL QTY','ITEM COUNT','TOTAL SAVINGS',
    'AVERAGE / PAX','AVERAGE/PAX','TAX TOTAL','GST SUMMARY','TAX SUMMARY',
    'SERVICE CHARGE','SERV. CHARGE','ROUNDING ADJ','ROUNDING ADJUSTMENT',
    'AMT EXCL GST','AMT. EXCL. GST','AMOUNT EXCL GST','TOTAL EXCL GST','TOTAL EXCLUDING GST','EXCL. GST',
]

QUALIFIER_DOWNGRADE = [
    'INCLUSIVE OF GST','INCL GST','INCL. GST','INCLUDING GST',
    'EXCLUSIVE OF GST','EXCL GST','EXCL. GST','EXCLUDING GST',
    'BEFORE ROUNDING','GROSS',
]

def _normalize(line):
    return re.sub(r'\s+', ' ', line.strip().upper())

def _nospace(s):
    return re.sub(r'\s+', '', s)

def _line_is_excluded(norm_line):
    return any(kw in norm_line for kw in EXCLUSIONS)

def _tier_match(norm_line, tier_keywords):
    ns_line = _nospace(norm_line)
    for kw in tier_keywords:
        if kw in norm_line:
            return True
        if _nospace(kw) in ns_line:
            return True
    return False

def _is_qualifier_line(norm_line):
    return any(q in norm_line for q in QUALIFIER_DOWNGRADE)

def _rounding_adj_proximity(norm_lines, i, window=4):
    # True if a ROUNDING ADJ line appears within `window` lines before i
    for j in range(max(0, i-window), i):
        if 'ROUNDING ADJ' in norm_lines[j] or 'ROUNDING ADJUSTMENT' in norm_lines[j]:
            return True
    return False

def _is_plain_keyword_start(norm_line, tier_keywords):
    # True when the keyword is at the start of the normalised line (plain final TOTAL style),
    # and the line is not a qualifier line.
    for kw in tier_keywords:
        if norm_line.startswith(kw) and not _is_qualifier_line(norm_line):
            return True
    return False

def extract_total_from_text(text):
    raw = [ln for ln in text.splitlines() if ln.strip()]
    norm = [_normalize(ln) for ln in raw]

    for tier_idx, tier in enumerate(TIERS):
        cands = []  # (line_index, value, is_qualifier, after_rounding_adj, is_plain_start)
        for i, nln in enumerate(norm):
            if _line_is_excluded(nln):
                continue
            if not _tier_match(nln, tier):
                continue
            v = last_strict_number(raw[i])
            if v is None:
                # Two-line fallback: ONLY when the keyword line has no digits at all
                if not re.search(r'\d', raw[i]):
                    for j in range(i+1, min(i+3, len(raw))):
                        if not raw[j].strip():
                            continue
                        if _line_is_excluded(norm[j]):
                            break
                        v2 = last_strict_number(raw[j]) or last_loose_number(raw[j])
                        if v2 is not None:
                            cands.append((j, v2, _is_qualifier_line(nln), _rounding_adj_proximity(norm, j), False))
                            break
                continue
            cands.append((i, v, _is_qualifier_line(nln), _rounding_adj_proximity(norm, i), _is_plain_keyword_start(nln, tier)))

        if not cands:
            continue

        # Preference within tier (higher wins):
        # 1) after a 'ROUNDING ADJ' line (final rounded total)
        # 2) plain-keyword-start lines over qualifier lines (final 'TOTAL:' > 'Total (Inclusive of GST)')
        # 3) non-qualifier over qualifier
        # 4) latest (bottom-most) in reading order
        cands.sort(key=lambda c: (c[3], c[4], not c[2], c[0]), reverse=True)
        return cands[0][1]
    return None
```

### Cross-anchor sanity check (catches isolated OCR digit flips)

After picking a candidate `T`, compute anchor values from the SAME OCR text: the set of monetary values appearing on lines labelled with any of the anchor labels below. Anchors are evidence that a value is the receipt's authoritative total.

- If an anchor value `A` appears on 2 or more such lines (consensus) and differs from `T` by more than 0.05, prefer `A`.
- If a SINGLE strong anchor (`TOTAL ROUNDED`, `ROUNDED TOTAL`, `TOTAL AFTER ROUNDING`, `TOTAL RM INCLUDING GST`, `GRAND TOTAL`, or Cash − Change) exists and differs from `T` by more than 0.05, prefer that anchor.
- When computing Cash − Change, use the matching Cash/Change pair from the same text; the resulting value is a strong anchor.

```python
STRONG_ANCHOR_LABELS = ['TOTAL ROUNDED','ROUNDED TOTAL','TOTAL AFTER ROUNDING','GRAND TOTAL','TOTAL RM INCLUDING GST','TOTAL RM INCL GST','NET TOTAL','NETT TOTAL']
WEAK_ANCHOR_LABELS = ['SUBTOTAL','SUB TOTAL','SUB-TOTAL','TOTAL (INCLUSIVE OF GST)','TOTAL INCL GST','TOTAL INCLUSIVE OF GST','TOTAL INCL. OF GST','PAYMENT','VISA','MASTERCARD','DEBIT','CREDIT CARD']

def _line_label_matches(norm_line, labels):
    return any(lbl in norm_line for lbl in labels)

def anchor_values(text):
    strong, weak = [], []
    norm_lines = []
    raw_lines = []
    for ln in text.splitlines():
        if not ln.strip():
            continue
        raw_lines.append(ln)
        norm_lines.append(_normalize(ln))
    for ln, nln in zip(raw_lines, norm_lines):
        if _line_label_matches(nln, STRONG_ANCHOR_LABELS):
            v = last_strict_number(ln)
            if v is not None:
                strong.append(abs(v))
        elif _line_label_matches(nln, WEAK_ANCHOR_LABELS):
            v = last_strict_number(ln)
            if v is not None:
                weak.append(abs(v))
    # Cash − Change consensus (strong anchor)
    cash = change = None
    for ln, nln in zip(raw_lines, norm_lines):
        if 'CASH' in nln and 'TENDERED' not in nln and cash is None:
            v = last_strict_number(ln)
            if v is not None:
                cash = v
        if 'CHANGE' in nln and change is None:
            v = last_strict_number(ln)
            if v is not None:
                change = v
    if cash is not None and change is not None:
        strong.append(round(cash - change, 2))
    return strong, weak

def reconcile_total(text, chosen):
    if chosen is None:
        return None
    strong, weak = anchor_values(text)
    from collections import Counter
    # 1) Strong single-anchor override: any strong anchor value disagreeing with chosen by >0.05
    for s in strong:
        if abs(s - chosen) > 0.05:
            # Count how many anchors (strong + weak) agree with s vs chosen
            agree_s = sum(1 for v in strong+weak if abs(v - s) <= 0.05)
            agree_c = sum(1 for v in strong+weak if abs(v - chosen) <= 0.05)
            if agree_s >= agree_c:
                return round(s, 2)
    # 2) Weak consensus (≥2 agreeing weak anchors on a different value)
    counts = Counter(round(v, 2) for v in weak)
    if counts:
        best_anchor, best_count = counts.most_common(1)[0]
        if best_count >= 2 and abs(best_anchor - chosen) > 0.05:
            return best_anchor
    return chosen
```

### Date extraction (ISO output, DD/MM default, labelled-line preferred, sanity-checked)

```python
MONTHS = {m.upper(): i for i, m in enumerate(
    ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], start=1)}
MONTHS_FULL = {m.upper(): i for i, m in enumerate(
    ['January','February','March','April','May','June','July','August','September','October','November','December'], start=1)}

def _valid_ymd(y, m, d):
    try:
        datetime(y, m, d)
        return 1990 <= y <= 2100
    except ValueError:
        return False

def _parse_numeric_date(a, b, c):
    if len(a) == 4:
        y, m, d = int(a), int(b), int(c)
        if _valid_ymd(y, m, d):
            return y, m, d
        return None
    if len(c) == 4:
        y = int(c); d = int(a); mo = int(b)
        # Prefer DD/MM/YYYY; fall back to MM/DD/YYYY only if DD/MM invalid
        if _valid_ymd(y, mo, d):
            return y, mo, d
        if _valid_ymd(y, d, mo):
            return y, d, mo
        return None
    y = 2000 + int(c) if int(c) < 100 else int(c)
    d, mo = int(a), int(b)
    if _valid_ymd(y, mo, d):
        return y, mo, d
    if _valid_ymd(y, d, mo):
        return y, d, mo
    return None

DATE_LABEL_RE = re.compile(r'(?i)\b(date|tarikh|invoice\s*date|receipt\s*date|bill\s*date|trans(?:action)?\s*date|tax\s*invoice\s*date|order\s*date|data)\b')
NUM_DATE_RE = re.compile(r'(\d{1,4})[\-/\.](\d{1,2})[\-/\.](\d{2,4})')
TEXT_DATE_RE = re.compile(r'(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})')

def extract_date_from_text(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    labelled, unlabelled = [], []
    for ln in lines:
        bucket = labelled if DATE_LABEL_RE.search(ln) else unlabelled
        for m in NUM_DATE_RE.finditer(ln):
            bucket.append(('num', m.group(1), m.group(2), m.group(3)))
        for m in TEXT_DATE_RE.finditer(ln):
            bucket.append(('txt', m.group(1), m.group(2), m.group(3)))
    for group in (labelled, unlabelled):
        for item in group:
            if item[0] == 'num':
                r = _parse_numeric_date(item[1], item[2], item[3])
                if r:
                    y, mo, d = r
                    return f'{y:04d}-{mo:02d}-{d:02d}'
            else:
                d = int(item[1]); mo_name = item[2].upper(); y = int(item[3])
                mo = MONTHS.get(mo_name[:3]) or MONTHS_FULL.get(mo_name)
                if mo and _valid_ymd(y, mo, d):
                    return f'{y:04d}-{mo:02d}-{d:02d}'
    return None
```

Notes:
- Labelled-line candidates (lines containing `Date`, `Tarikh`, `Invoice Date`, `Data` [common OCR of `Date`], etc.) are tried first before any other date-looking token.
- `_parse_numeric_date` prefers DD/MM/YYYY over MM/DD/YYYY when both parse; this matches the dominant convention on RM/GST-style receipts.
- Years must be in [1990, 2100]; otherwise the candidate is rejected and the next is tried.

### Format and null contract

- `date`: `'YYYY-MM-DD'` string or Python `None`.
- `total_amount`: Python string with exactly two decimals via `f'{v:.2f}'` or Python `None`. Never a float, never `''`, never `'None'`, never `NaN`.

```python
def format_amount(v):
    return None if v is None else f'{v:.2f}'
```

## Per-image pipeline with multi-pass arbitration

```python
def extract_fields(image_path):
    texts = ocr_variants(image_path)
    date_candidates, total_candidates = [], []
    for t in texts:
        d = extract_date_from_text(t)
        if d:
            date_candidates.append(d)
        v = extract_total_from_text(t)
        v = reconcile_total(t, v)
        if v is not None:
            total_candidates.append(round(v, 2))
    from collections import Counter
    date = Counter(date_candidates).most_common(1)[0][0] if date_candidates else None
    total = Counter(total_candidates).most_common(1)[0][0] if total_candidates else None
    return date, format_amount(total)
```

## Batch Pipeline to Tabular Output (strict null preservation)

Use openpyxl directly so `None` becomes a truly empty cell (not `''`, not `'None'`, not `NaN`). Keep `total_amount` as a text cell (`number_format='@'`) so strings like `'20.00'` survive round-trip.

```python
IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}

def process_receipts(img_dir, out_xlsx):
    from openpyxl import Workbook
    files = sorted(f for f in os.listdir(img_dir) if Path(f).suffix.lower() in IMG_EXTS)
    wb = Workbook()
    ws = wb.active
    ws.title = 'results'
    ws.append(['filename', 'date', 'total_amount'])
    for fn in files:
        try:
            date_val, amount_val = extract_fields(os.path.join(img_dir, fn))
        except Exception:
            date_val, amount_val = None, None
        # Explicit None preservation: write None (empty cell), never '' or 'None'.
        row_idx = ws.max_row + 1
        ws.cell(row=row_idx, column=1, value=fn)
        ws.cell(row=row_idx, column=2, value=date_val if date_val else None)
        ws.cell(row=row_idx, column=3, value=amount_val if amount_val else None)
        ws.cell(row=row_idx, column=3).number_format = '@'
    wb.save(out_xlsx)
```

## Critical Rules for Receipt Extraction

- Exclusions are applied FIRST on each line.
- Priority tiers are tried in order; move to the next tier only when the current tier yields no candidates.
- Within a tier, prefer in this order: (1) a line that follows a `ROUNDING ADJ` line within a 4-line window (final rounded total); (2) plain-keyword-start lines (e.g. bare `TOTAL:`) over qualifier lines (`Total (Inclusive of GST)`, `Before Rounding`); (3) non-qualifier lines over qualifier lines; (4) the latest (bottom-most) line in reading order.
- Keyword matching tolerates missing whitespace (`GRANDTOTAL`, `TOTALRM`) via a nospace secondary match.
- Two-line fallback triggers ONLY when the keyword line contains no digits at all; the fallback line must itself pass the exclusion filter.
- Cross-anchor sanity: strong anchors (`TOTAL ROUNDED`, `ROUNDED TOTAL`, `GRAND TOTAL`, `TOTAL RM INCLUDING GST`, `NET TOTAL`, Cash−Change) override the chosen value when they disagree by >0.05 and are at least as well-supported; weak anchors require ≥2 agreeing values to override.
- Numbers: strip currency prefixes (`RM`, `$`, `MYR`) and commas; strip leading `-` for negative-payment anchors like Visa; repair in-token `:`→`.`; prefer strict two-decimal matches; use loose matches only as last resort.
- Dates: prefer labelled-line candidates (lines containing `Date`, `Data`, `Tarikh`, `Invoice Date`, etc.); default to DD/MM/YYYY when both DD/MM and MM/DD parse; reject years outside 1990–2100 and invalid day/month combinations.
- Null on failure means Python `None` written as an empty Excel cell. Keep `total_amount` as a 2-decimal string (`f'{v:.2f}'`) when present.
- Per-image failures must degrade to `(None, None)` without aborting the batch.
- Run extraction PER OCR pass and arbitrate by majority value; never concatenate variant texts before extraction.

## Common Pitfalls

- Choosing a pre-rounding `Total (Inclusive of GST)` line when a later plain `TOTAL:` line after `Rounding Adj` is the final payable amount.
- Picking a payment line (`Cash Received`, `Visa`, `Mastercard`) via the two-line fallback.
- Writing `''` or `'None'` or `NaN` for failed fields, which fail strict null-equality verifiers.
- Writing a float like `47.7` instead of the string `'47.70'`.
- Confusing DD/MM and MM/DD on ambiguous dates (both components ≤ 12) due to no documented default.
- Accepting a 1-decimal OCR truncation like `88.1` as a valid monetary total when a 2-decimal candidate exists in another variant.
- Letting a single-variant OCR digit flip (e.g. `102`→`702`, `538`→`702`) win when strong anchors (`Total Rounded`, `Total RM Including GST`, Cash−Change) all agree on another value.
- Requiring exact whitespace between `GRAND` and `TOTAL`: OCR commonly glues these into `GRANDTOTAL`.

## Quality Self-Check

- [ ] All image files in the input directory are processed (filtered by extension) and rows are sorted lexicographically by filename.
- [ ] `date` is `'YYYY-MM-DD'` or Python `None`.
- [ ] `total_amount` is a Python string matching `^\d+\.\d{2}$` or Python `None`.
- [ ] Exclusion keywords never source the total; qualifier lines are deprioritized when a cleaner candidate exists.
- [ ] Rounding-aware preference and cross-anchor sanity are applied; strong anchors can override on their own.
- [ ] None values become empty cells in the output workbook (verify by reloading with openpyxl and asserting `cell.value is None`).
- [ ] Exactly one sheet named `results` with exactly the required columns in the required order.

## Tesseract Configuration Reference

```python
# PSM 6: uniform block of text (default for receipts)
# PSM 4: single column, variable sizes
# PSM 11: sparse text
text = pytesseract.image_to_string(img, config='--psm 6', lang='eng')
```

## Limitations

- Tesseract is weakest on handwriting, decorative fonts, and severely degraded scans.
- Ambiguous dates where both components ≤ 12 and no label is present are resolved by the DD/MM default; some will still be wrong when the receipt uses MM/DD.
- OCR digit confusions (`1`↔`7`, `0`↔`O/Q`, `5`↔`S`, `8`↔`B`) can still produce wrong totals when no anchor consensus exists.
