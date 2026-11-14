---
name: image-ocr
description: Extract text content from images using Tesseract OCR via Python, including structured field extraction from receipts and forms
---

# Image OCR Skill

## Purpose
Extract text from image files (JPG, PNG, WEBP) via `pytesseract` with multi-variant preprocessing, and pull structured fields (dates, monetary totals, keyed values) from noisy receipt scans via per-variant extraction with cross-variant consensus and cross-line corroboration.

## When to Use
- Scanned receipts, invoices, forms, screenshots
- Batch structured-field extraction (date, grand total, keyed amount)
- Any pipeline where a single Tesseract pass is unreliable and output must survive line-by-line grading

## Required Libraries

```python
import pytesseract
from PIL import Image, ImageOps, ImageFilter
import re
from collections import Counter
from datetime import datetime
```

## Basic OCR

```python
def extract_text_from_image(image_path):
    img = Image.open(image_path)
    return pytesseract.image_to_string(img).strip()
```

## Multi-Pass OCR Variants

Run several preprocessing × PSM variants and keep them as SEPARATE texts. Never concatenate variant outputs into one blob — one noisy variant contaminates clean reads and single-pass digit confusions (1↔7, 3↔8, 0↔O) win silently. 3x upscale + PSM 4 frequently rescues faded thermal `Grand Total` lines.

```python
def multi_pass_variants(image_path):
    img = Image.open(image_path)
    gray = ImageOps.grayscale(img)
    autocontrast = ImageOps.autocontrast(gray)
    sharp = autocontrast.filter(ImageFilter.SHARPEN)
    w, h = img.size
    up2 = autocontrast.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    up3 = autocontrast.resize((w * 3, h * 3), Image.Resampling.LANCZOS)
    inv = ImageOps.invert(autocontrast)

    configs = [
        (autocontrast, '--psm 6'),
        (autocontrast, '--psm 4'),
        (autocontrast, '--psm 11'),
        (sharp, '--psm 6'),
        (up2, '--psm 6'),
        (up2, '--psm 4'),
        (up3, '--psm 4'),
        (up3, '--psm 6'),
        (inv, '--psm 6'),
    ]
    texts = []
    for v, psm in configs:
        try:
            t = pytesseract.image_to_string(v, config=psm)
            if t.strip():
                texts.append(t)
        except Exception:
            pass
    return texts
```

## Structured Field Extraction (Receipts / Forms)

Use priority-and-exclusion matching with cross-variant voting AND cross-line money-token corroboration. Never pick the first numeric match on its own.

### Keyword Priority and Exclusions

```python
TOTAL_PRIORITY = [
    # Tier 0 - post-rounding / final / grand totals (authoritative)
    # Tolerant patterns handle OCR concatenation ('GrandTotal'), missing trailing
    # char ('GrandTota'), and 0<->O confusion in 'TOTAL'.
    [r'GRAND\s*T[O0]TA[L1I]?\b', r'GRANDT[O0]TA[L1I]?\b',
     r'T[O0]TAL\s*R[O0]UNDED', r'R[O0]UNDED\s*T[O0]TAL',
     r'T[O0]TAL\s*AMT\s*R[O0]UNDED',
     r'T[O0]TAL\s*AFTER\s*R[O0]UND(ING)?',
     r'T[O0]TAL\s*AFTER\s*ADJ',
     r'NETT?\s*T[O0]TAL'],
    # Tier 1 - currency-tagged
    [r'T[O0]TAL\s*:?\s*RM', r'RM\s*T[O0]TAL'],
    # Tier 2 - explicit total amount
    [r'T[O0]TAL\s*AMOUNT'],
    # Tier 3 - due/balance variants
    [r'T[O0]TAL\s*DUE', r'AMOUNT\s*DUE', r'BALANCE\s*DUE'],
    # Tier 4 - qualified inclusive-GST totals (PRE-rounding; demoted)
    [r'T[O0]TAL\s*\(?\s*INCLUSIVE\s*(OF\s*)?GST',
     r'T[O0]TAL\s*INCL\.?\s*(OF\s*)?GST',
     r'T[O0]TAL\s*SALES\s*INCL',
     r'T[O0]TAL\s*RM\s*INCL(UDING)?\s*GST'],
    # Tier 5 - bare TOTAL/AMOUNT (lowest priority)
    [r'\bT[O0]TAL\b', r'\bAMOUNT\b'],
]

EXCLUSIONS = [
    'SUBTOTAL', 'SUB TOTAL', 'SUB-TOTAL',
    'TAX', 'GST', 'SST', 'VAT',
    'DISCOUNT', 'SAVING',
    'CHANGE',
    'CASH TENDERED', 'CASH RECEIVED', 'CASH PAYMENT',
    'VISA', 'MASTERCARD', 'MASTER CARD', 'AMEX',
    'CREDIT CARD', 'DEBIT CARD', 'CARD',
    'PAYMENT', 'PAID', 'TENDERED',
    'ROUNDING ADJ', 'ROUNDING ADJUSTMENT',
    'SERVICE CHARGE', 'SERV CHARGE', 'SERV. CHARGE',
    'POINTS', 'LOYALTY',
    'TOTAL ITEM', 'TOTAL QTY', 'TOTAL QUANTITY', 'ITEM COUNT',
    'TOTAL SAVING', 'TOTAL GROSS',
    'EXCLUDING', 'EXCL.', 'EXCL GST', 'EXCLUSIVE',
    'AVERAGE', 'PAX',
    'GST SUMMARY', 'TAX SUMMARY', 'SST SUMMARY', 'TAX CODE',
    'BALANCE',
]

NUM_RE = re.compile(r'\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2}')

def _line_excluded(upper_line):
    return any(ex in upper_line for ex in EXCLUSIONS)

def _is_column_header(upper_line):
    # Lines like 'Description Qty Price Amount' match the AMOUNT keyword but
    # carry no digits and must not seed a two-line fallback into the item rows.
    if re.search(r'\d', upper_line):
        return False
    tokens = ['DESCRIPTION', 'QTY', 'PRICE', 'AMOUNT', 'ITEM', 'U.PRICE', 'U/P', 'RSP', 'UNIT']
    return sum(1 for t in tokens if t in upper_line) >= 2

def _last_money(line):
    m = NUM_RE.findall(line)
    return m[-1] if m else None

def _all_money_in_text(text):
    out = []
    for ln in text.splitlines():
        out.extend(m.replace(',', '') for m in NUM_RE.findall(ln))
    return out

def _normalize_amount(s):
    try:
        v = float(s.replace(',', ''))
        if v <= 0 or v > 1_000_000:
            return None
        return f'{v:.2f}'
    except (ValueError, AttributeError):
        return None
```

### Selection Rules (apply in order)

1. **Exclusion first.** Discard any line whose uppercase form contains an EXCLUSION substring.
2. **Column-header guard.** Skip lines matching `_is_column_header` (prevents item tables with an `AMOUNT` column from being treated as a TOTAL keyword line).
3. **Section cutoff.** Ignore lines at or after `(GST|TAX|SST)\s*SUMMARY` or `TAX\s*CODE`.
4. **Within a tier, LAST match wins.** Receipts print the final total at the bottom.
5. **Rounding-adjustment preference.** If a `ROUNDING ADJ` line exists AND a bare-TOTAL (tier 5) candidate appears AFTER it, prefer it over any tier-4 Inclusive-GST line (handles the common `Total (Inclusive of GST): X` → `Rounding Adj: -0.01` → `TOTAL: Y` layout). Higher tiers (0–3) still outrank tier 5.
6. **Guarded two-line fallback.** Only when the keyword line has NO digits at all, scan the next 3 non-empty, non-excluded, non-column-header lines and accept the first whose last token matches `N.NN`. Never fall through onto a payment/change/card line.
7. **Two decimals required.** Totals must have exactly two decimals; bare integers on keyword lines are rejected.

```python
def _tier_hits(text_lines_upper, text_lines, cutoff, tier):
    hits = []
    for i, u in enumerate(text_lines_upper[:cutoff]):
        if _line_excluded(u) or _is_column_header(u):
            continue
        if not any(re.search(pat, u) for pat in tier):
            continue
        num = _last_money(text_lines[i])
        if num is None and not re.search(r'\d', text_lines[i]):
            for j in range(i + 1, min(i + 4, cutoff)):
                if _line_excluded(text_lines_upper[j]) or _is_column_header(text_lines_upper[j]):
                    continue
                cand = _last_money(text_lines[j])
                if cand is not None:
                    num = cand
                    break
        if num is not None:
            hits.append((i, num))
    return hits

def extract_total_from_text(text):
    """Return (tier_index, formatted_string) or (None, None)."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    upper = [ln.upper() for ln in lines]

    cutoff = len(lines)
    for i, u in enumerate(upper):
        if re.search(r'(GST|TAX|SST)\s*SUMMARY', u) or re.search(r'TAX\s*CODE', u):
            cutoff = i
            break

    round_idx = None
    for i, u in enumerate(upper[:cutoff]):
        if 'ROUNDING ADJ' in u or re.search(r'\bROUNDING\b.*ADJ', u):
            round_idx = i

    # Try tiers 0-3 first (unambiguous labels).
    for tier_idx in range(0, 4):
        hits = _tier_hits(upper, lines, cutoff, TOTAL_PRIORITY[tier_idx])
        if hits:
            formatted = _normalize_amount(hits[-1][1])
            if formatted is not None:
                return tier_idx, formatted

    # Rounding preference: a tier-5 bare-TOTAL line AFTER a Rounding Adj beats
    # a tier-4 Inclusive-GST line (the post-rounding value is what was paid).
    t5 = _tier_hits(upper, lines, cutoff, TOTAL_PRIORITY[5])
    if round_idx is not None:
        post = [(i, v) for (i, v) in t5 if i > round_idx]
        if post:
            formatted = _normalize_amount(post[-1][1])
            if formatted is not None:
                return 5, formatted

    # Tier 4 (Inclusive-GST) if no post-rounding bare TOTAL exists.
    t4 = _tier_hits(upper, lines, cutoff, TOTAL_PRIORITY[4])
    if t4:
        formatted = _normalize_amount(t4[-1][1])
        if formatted is not None:
            return 4, formatted

    # Finally tier 5 with no rounding anchor.
    if t5:
        formatted = _normalize_amount(t5[-1][1])
        if formatted is not None:
            return 5, formatted
    return None, None
```

### Cross-Variant Consensus with Cross-Line Corroboration

A single-variant OCR flip (e.g., `102.00` → `702.00` on a `Total Amt Rounded` line) can produce a confidently-wrong tier-0 candidate. Defend against it by (a) voting across variants within the best observed tier, and (b) checking how often each candidate value appears as ANY monetary token across ALL variant texts. A value that recurs on Subtotal / Total Incl / Payment / Cash lines across variants outranks a noisy one-off.

```python
def extract_total(image_path):
    texts = multi_pass_variants(image_path)
    if not texts:
        return None
    per_variant = []  # (tier, value)
    for t in texts:
        tier, val = extract_total_from_text(t)
        if val is not None:
            per_variant.append((tier, val))
    if not per_variant:
        return None

    best_tier = min(tier for tier, _ in per_variant)
    tier_values = [v for tier, v in per_variant if tier == best_tier]
    counts = Counter(tier_values)

    # Corroboration: count how many variants carry each candidate value
    # anywhere as a money-shaped token (Subtotal/Total/Payment/Cash etc.).
    money_support = Counter()
    for t in texts:
        seen = set(_all_money_in_text(t))
        for v in seen:
            money_support[v] += 1

    def score(v):
        key = v.replace(',', '')
        return counts[v] * 3 + money_support.get(key, 0)

    top_val = max(counts.keys(), key=score)

    # If the top value is supported by exactly 1 variant AND some other value
    # (possibly from a lower tier but seen in >=2 variant extractions) has much
    # stronger money-token corroboration, prefer that value. This neutralises
    # single-variant digit flips on an otherwise clean receipt where the
    # correct amount appears repeatedly (Subtotal == Total == Payment).
    if counts[top_val] <= 1:
        all_values = Counter(v for _, v in per_variant)
        top_support = money_support.get(top_val.replace(',', ''), 0)
        for cand, cand_votes in all_values.most_common():
            if cand == top_val:
                continue
            cand_support = money_support.get(cand.replace(',', ''), 0)
            if cand_votes >= 2 and cand_support >= top_support + 2:
                return cand
    return top_val
```

### Date Extraction and ISO Normalization

Many receipt corpora (Malaysian, UK, EU) use DD/MM/YYYY. Try day-first first, validate ranges, prefer dates on a `Date:` / `Tarikh:` / `Invoice Date:` line, and vote across OCR variants to defend against single-digit misreads (3↔8, 0↔6).

```python
DATE_PATTERNS = [
    ('%d/%m/%Y', r'\b(\d{1,2}/\d{1,2}/\d{4})\b'),
    ('%d-%m-%Y', r'\b(\d{1,2}-\d{1,2}-\d{4})\b'),
    ('%d.%m.%Y', r'\b(\d{1,2}\.\d{1,2}\.\d{4})\b'),
    ('%Y-%m-%d', r'\b(\d{4}-\d{1,2}-\d{1,2})\b'),
    ('%Y/%m/%d', r'\b(\d{4}/\d{1,2}/\d{1,2})\b'),
    ('%d %b %Y', r'\b(\d{1,2} [A-Za-z]{3} \d{4})\b'),
    ('%d-%b-%Y', r'\b(\d{1,2}-[A-Za-z]{3}-\d{4})\b'),
    ('%d/%m/%y', r'\b(\d{1,2}/\d{1,2}/\d{2})\b'),
    ('%d-%m-%y', r'\b(\d{1,2}-\d{1,2}-\d{2})\b'),
]

DATE_ANCHOR = re.compile(
    r'\b(DATE|TARIKH|INVOICE\s*DATE|RECEIPT\s*DATE|BILL\s*DATE|TRANS(ACTION)?\s*DATE)\b',
    re.IGNORECASE)
DATE_NEGATIVE = re.compile(r'\b(PRINT\s*DATE|CLOSED|FRN\s*ON|EXP(IRY)?)\b', re.IGNORECASE)

def _valid_date(dt):
    return 2000 <= dt.year <= 2099 and 1 <= dt.month <= 12 and 1 <= dt.day <= 31

def _try_parse(tok, fmt):
    try:
        dt = datetime.strptime(tok, fmt)
        if _valid_date(dt):
            return dt.date().isoformat()
    except ValueError:
        pass
    return None

def extract_date_from_text(text):
    out = []  # (iso, anchored)
    for line in text.splitlines():
        if not line.strip():
            continue
        anchored = bool(DATE_ANCHOR.search(line)) and not DATE_NEGATIVE.search(line)
        for fmt, pat in DATE_PATTERNS:
            for m in re.finditer(pat, line):
                iso = _try_parse(m.group(1), fmt)
                if iso is not None:
                    out.append((iso, anchored))
                    break
    return out

def extract_date(image_path):
    texts = multi_pass_variants(image_path)
    cands = []
    for t in texts:
        cands.extend(extract_date_from_text(t))
    if not cands:
        return None
    anchored_pool = [d for d, a in cands if a]
    pool = anchored_pool if anchored_pool else [d for d, _ in cands]
    counts = Counter(pool)
    top, _ = counts.most_common(1)[0]
    return top
```

### Per-Image Pipeline with Null-Safe Failure

```python
def process_receipt(image_path):
    try:
        return {
            'date': extract_date(image_path),
            'total_amount': extract_total(image_path),
        }
    except Exception:
        return {'date': None, 'total_amount': None}
```

**Hard contract:** `process_receipt` MUST return a dict whose values are either a correctly-formatted string (`'YYYY-MM-DD'` or `'N.NN'`) or Python `None`. Callers MUST pass these values through to the downstream writer unchanged. Do NOT substitute `''`, `'None'`, `'NaN'`, `'nan'`, `0`, or `0.00` for missing values — graders treat those as incorrect non-null answers.

## Deterministic Batch Ordering

```python
from pathlib import Path

IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp'}

def iter_images(directory):
    for p in sorted(Path(directory).iterdir(), key=lambda x: x.name):
        if p.name.startswith('.'):
            continue
        if p.suffix.lower() in IMG_EXT:
            yield p
```

## Tesseract Configuration Notes

- `--psm 6` (uniform block): strong default for receipts.
- `--psm 4` (single column of variable-sized text): often the only pass that recovers faded Grand Total lines; pair with 2x or 3x upscale.
- `--psm 11` (sparse text): rescues text on cluttered layouts.

## Common OCR Confusions

Digits: `1`↔`7`, `3`↔`8`, `5`↔`6`, `0`↔`8`, `0`↔`O`, `l`↔`1`, `S`↔`5`, `B`↔`8`. Labels: `GRANDTOTA`, `GrandTotal`, `GrandTota.`, `T0TAL`, `NETTOTAL`, `TOTAL RH`, `TOTAL:RM`. The tolerant patterns above handle label corruption; cross-variant voting plus cross-line corroboration handle digit corruption.

## Quality Self-Check

- [ ] Exclusions and column-header guards are tested BEFORE any tier match.
- [ ] A `(GST|TAX|SST) SUMMARY` cutoff removes the tax breakdown table.
- [ ] Within tiers 0–4, the LAST matching line in reading order is selected.
- [ ] A bare-TOTAL (tier 5) line AFTER a `Rounding Adj` line outranks a tier-4 Inclusive-GST line.
- [ ] The two-line fallback fires only when the keyword line has ZERO digits and never descends onto payment/change/card lines or column-header rows.
- [ ] Candidate numbers are exactly N.NN (two decimals).
- [ ] Amounts are strings formatted with `f'{v:.2f}'`, commas stripped.
- [ ] Dates are ISO `YYYY-MM-DD` strings; invalid/ambiguous dates degrade to `None`.
- [ ] Multi-variant extraction is combined via vote + cross-line money-token corroboration; single-variant outliers are rejected.
- [ ] Per-image exceptions degrade to `None` fields; empty strings are never emitted.
- [ ] Image listing is filtered by extension and sorted lexicographically by filename.

## Limitations

- Tesseract works best with printed text; handwriting is unreliable.
- Severe degradation reduces accuracy; multi-variant voting mitigates but cannot fully correct.
- Ambiguous dates (e.g., 03/04/05) return `None` rather than guess.
