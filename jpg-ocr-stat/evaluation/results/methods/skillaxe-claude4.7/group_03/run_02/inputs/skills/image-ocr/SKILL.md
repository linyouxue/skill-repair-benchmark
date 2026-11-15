---
name: image-ocr
description: Extract text content from images using Tesseract OCR via Python
---

# Image OCR Skill

## Purpose
Extract text from images (JPG/PNG/etc.) using Tesseract (`pytesseract`) with receipt-friendly preprocessing and downstream parsing guidance.

## When to Use
- Scanned receipts/invoices where you must extract specific fields (e.g., date, total)
- Batch OCR over many images

## Required Libraries
```python
import pytesseract
from PIL import Image, ImageFilter, ImageOps
import os
import re
```

## Practical OCR Guidance for Receipts

### 1) Preserve line structure
Receipt parsing depends on line breaks. Prefer `image_to_string` outputs with newlines preserved.

### 2) Use a strong default OCR baseline first
Many receipt failures are OCR-quality failures.

**Recommended baseline (try first):**
- Preprocess: **grayscale + autocontrast**
- OCR config: `--psm 6` (uniform block; strong default for receipts)

Only if the baseline fails, try additional variants.

### 3) Minimal preprocessing variants (small set)
Try these variants (in order):
1. Grayscale + autocontrast (baseline)
2. Grayscale + autocontrast + sharpen
3. Thresholded (binary) at 1–2 thresholds
4. Invert only if white-on-dark

**Upscaling (high leverage for small/faint receipts)**
- If the shortest side is small (rule of thumb: `< 900px`) or OCR drops/merges digits (e.g., `1`→`7`), run an additional pass on a **2× upscaled** image.
- If totals are still garbled (missing decimal point, keyword partially missing), add a **3× upscaled** pass and try `--psm 4` (single column) as a targeted fallback.
- Upscaling can fix digit-merge errors on totals, but can also introduce new errors; treat it as an additional candidate source.

### 4) Multi-pass OCR: select best *field* candidate, don’t concatenate
Concatenating multi-pass text can introduce duplicate/conflicting totals.
Instead:
- run multiple OCR passes
- extract date/total candidates per pass
- score candidates and keep the best

**Important:** Some receipts OCR better *without* preprocessing. If the baseline pass yields low-quality text (missing decimals, heavy garbage), also run a raw/default pass and treat it as another candidate source.

## Field Extraction Heuristics (Receipts)

### Date extraction (reduce false positives)
Receipts often contain multiple date-like strings (header date/time vs print date vs other numeric IDs).

**Candidate generation**
- Accept common formats:
  - `dd/mm/yyyy`, `dd-mm-yyyy`, `dd/mm/yy`, `dd-mm-yy`
  - `yyyy-mm-dd`
- Validate plausibility:
  - year in a reasonable range (e.g., 2000–2035)
  - month 1–12, day 1–31

**Candidate ranking (most important first)**
1. Prefer dates on lines with an explicit label (case-insensitive):
   - `DATE`, `DATED`, `DOC DATE`, `INVOICE DATE`
   - **Label-tolerant matching**: treat common OCR near-misses as labels too, e.g. `DAIE`, `DAtE`, `DATA`.
2. If multiple labeled dates exist, prefer the *primary header Date field*:
   - appears in the header block (top portion of receipt)
   - appears near other header keys like `INVOICE`, `RECEIPT`, `BILL NO`, `DOC #`, `CASHIER`, `TIME`
   - **Prefer a clean `Date:` line over secondary header lines** (e.g., `Salesperson ... Data: ...`) when both exist.
3. Prefer dates near a `TIME` token on the same/adjacent line.

**Ambiguity note**
- Do not “fix” ambiguous day/month swaps unless you have a strong cue.
- If forced, Malaysian receipts commonly use `dd/mm`, but only apply when both interpretations are valid.

### Total amount extraction (avoid subtotals/cash/change)
Receipts contain many amounts; the payable total is usually near the bottom and may be affected by rounding.

**Priority keywords (highest → lowest)**
1. `GRAND TOTAL`
2. `TOTAL RM`, `TOTAL: RM` (also tolerate OCR `RN` for `RM`)
3. `TOTAL AMOUNT`
4. `TOTAL ROUNDED`, `TOTAL AMT ROUNDED`, `AMOUNT ROUNDED`, `ROUNDED TOTAL`, `TOTAL AFTER ROUNDING`
5. `NETT TOTAL`, `NET TOTAL`, `TOTAL`, `AMOUNT`, `TOTAL DUE`, `AMOUNT DUE`, `BALANCE DUE`

**Label-tolerant matching for GRAND TOTAL (common OCR corruption)**
Treat these as GRAND TOTAL equivalents when scanning lines:
- missing space/punctuation: `GRANDTOTAL`, `GrandTotal.`, `GrandTota.`, `GRAND TOTA`, `GRAND TOTAI`

This matters because otherwise the extractor may fall back to weaker `TOTAL`/`AMOUNT` matches or even to payment lines.

**Exclusions (skip these as totals)**
Always exclude lines whose *primary meaning* is not the payable total:
- `SUBTOTAL`, `SUB TOTAL`
- `DISCOUNT`
- `CHANGE`
- `CASH TENDERED`, `CASH RECEIVED`, `CASH PAYMENT` (payment lines; not the payable total)
- **Item-count totals**: `TOTAL ITEM`, `TOTAL ITEMS`, `ITEM COUNT`, `TOTAL QTY`
- **Pre-tax totals**: `EXCL`, `EXCLUDING` (e.g., `Total (Excluding GST)`)

Also exclude **column headers** that contain `AMOUNT` but are not summary totals:
- lines like `Description Qty Price Amount`, `QTY PRICE AMOUNT`, `AMOUNT TAX`, etc.

**Important: GST/SST/TAX as modifiers**
Do **not** blanket-exclude every line containing `GST`/`SST`/`TAX`.
- Lines like `Total (Inclusive of GST)` can be the correct total.
- Exclude only when the line is clearly a tax-only total/summary (e.g., `GST Summary`, `Total GST`).

**Rounding handling (common exact-match failure) — HARD RULE**
If a rounding adjustment exists (`ROUNDING`, `ROUNDING ADJ`, `Rounding Adj`) and there is a later/final
`TOTAL` / `TOTAL ROUNDED` / `TOTAL AFTER ROUNDING` line, **always prefer the later/final total**.

**Split keyword/amount across lines (tight trigger)**
Use the “next line last number” fallback **only when the keyword line has no digits at all**.

Additionally, do **not** apply this fallback to **column-header** lines (e.g., `Description Qty Price Amount`) even though they contain `AMOUNT`.

**Anchor-driven outlier rejection (critical for OCR digit flips like 102.00→702.00)**
When multiple total-like candidates exist, do not rely on “last TOTAL wins” or “majority across OCR variants” alone.

1. Extract **anchor amounts** (if present):
   - `SUBTOTAL` amount
   - `PAYMENT` amount (or `VISA`, `MASTERCARD` charge amount)
   - `TOTAL AFTER ROUNDING` / `TOTAL ROUNDED` amount
2. If **two or more** anchors agree (exact match after normalization) and a candidate total differs,
   treat the candidate as an OCR outlier and reject it.
3. **Mechanical override (make it hard to miss):**
   - If `PAYMENT` exists and matches one candidate total, prefer the candidate matching `PAYMENT`.
   - If `SUBTOTAL` exists and matches one candidate total, prefer the candidate matching `SUBTOTAL`.
   - Only allow a “rounded total” line to override anchors if it is consistent with them (or differs only by a small rounding delta that is explicitly shown).

### Amount string normalization (critical for exact-match scoring)
When you extract a numeric amount:
- Remove currency markers (`RM`, `$`) and thousands separators (`,`)
- Normalize common OCR punctuation:
  - treat `:` or `;` between digits as `.` when it looks like a decimal separator (e.g., `92:80` → `92.80`)
- Output must be a string with **exactly two decimal places** (e.g., `"47.70"`).
- If extraction fails/uncertain: output **None/null**.
  - **Never** output an empty string.

**Drop-in final validation snippet (prevents empty-string bugs + fixes 92:80)**
```python
import re

def finalize_amount(maybe_amount_str):
    if maybe_amount_str is None:
        return None
    s = str(maybe_amount_str).strip()
    if not s:
        return None
    s = s.replace(',', '')
    # Normalize OCR decimal separators like 92:80 or 92;80
    s = re.sub(r'(\d)[:;](\d{2})\b', r'\1.\2', s)
    m = re.search(r'(\d+)(?:\.(\d{1,2}))?$', s)
    if not m:
        return None
    whole = m.group(1)
    frac = (m.group(2) or '00').ljust(2, '0')
    return f"{int(whole)}.{frac[:2]}"
```

## Code Example: receipt-oriented multi-pass OCR (texts kept separate)
```python
from PIL import Image, ImageOps, ImageFilter
import pytesseract


def _variants(img):
    g = ImageOps.grayscale(img)
    yield ImageOps.autocontrast(g)  # baseline
    yield ImageOps.autocontrast(g).filter(ImageFilter.SHARPEN)
    for t in (110, 140):
        yield ImageOps.autocontrast(g).point(lambda p, tt=t: 255 if p > tt else 0)


def ocr_receipt_texts(image_path):
    img = Image.open(image_path)

    # Include a raw/default pass because some receipts OCR better without preprocessing.
    texts = [pytesseract.image_to_string(img, lang='eng')]

    # Strong baseline first.
    psm_modes = ['--psm 6', '--psm 4', '--psm 11']
    for v in _variants(img):
        for psm in psm_modes:
            txt = pytesseract.image_to_string(v, lang='eng', config=psm)
            if txt and txt.strip():
                texts.append(txt)

    # Optional: add an upscaled pass as another candidate source.
    if min(img.size) < 900:
        big2 = img.resize((img.size[0] * 2, img.size[1] * 2))
        big2 = ImageOps.autocontrast(ImageOps.grayscale(big2))
        texts.append(pytesseract.image_to_string(big2, lang='eng', config='--psm 6'))

        # Harder fallback: 3× + PSM 4 can recover faint “Grand Total” lines.
        big3 = img.resize((img.size[0] * 3, img.size[1] * 3))
        big3 = ImageOps.autocontrast(ImageOps.grayscale(big3))
        texts.append(pytesseract.image_to_string(big3, lang='eng', config='--psm 4'))

    return texts
```

## Error Handling
- If OCR is empty/garbage, try a different PSM and a thresholded variant.
- If the receipt is rotated, try rotating 90/180 degrees and re-running OCR.

## Quality Self-Check
- [ ] Preserve newlines in OCR output
- [ ] Start with grayscale+autocontrast + `--psm 6` baseline
- [ ] Also consider a raw/default OCR pass as an additional candidate source
- [ ] Consider a 2× upscaled OCR pass as an additional candidate source (don’t blindly trust it)
- [ ] If totals/keywords are still garbled, consider a 3× upscaled + `--psm 4` pass as a targeted fallback
- [ ] Date: prefer label-adjacent, header-block candidates; validate plausibility
- [ ] Total: apply priority keywords + exclusions
- [ ] Exclude column-header lines containing `AMOUNT` (e.g., `Description Qty Price Amount`)
- [ ] Split-line fallback triggers only when keyword line has **no digits** and is **not** a column header
- [ ] If rounding adjustment exists and a later TOTAL exists: **take the later TOTAL**
- [ ] Apply anchor-driven outlier rejection (Subtotal/Payment/Rounded-total consistency)
- [ ] Normalize totals to exactly two decimals (including `92:80` → `92.80`)
- [ ] Final schema guard: empty/whitespace-only → **None/null** (never empty string)

## Limitations
- Tesseract accuracy drops on very faint ink, heavy blur, or extreme skew
- Complex multi-column layouts may require cropping or per-region OCR

## Version History
- **1.1.6** (2026-10-21): Added explicit exclusion of column-header lines containing AMOUNT; clarified that split-line fallback must not trigger on headers; added optional 3× upscale + PSM4 fallback for faint/garbled GRAND TOTAL lines; expanded GRAND TOTAL tolerant variants to include punctuation/no-space forms.
- **1.1.5** (2026-10-21): Added label-tolerant GRAND TOTAL matching; tightened split-line fallback trigger (only when keyword line has no digits); expanded cash-payment exclusions; emphasized that anchor-consistency must override OCR-variant majority voting for totals
- **1.1.4** (2026-10-21): Added explicit 2× upscaling as a candidate OCR pass; strengthened mechanical anchor-consistency override for totals; clarified header-date preference when multiple labeled dates exist; added explicit schema-guard checklist item
- **1.1.3** (2026-10-21): Added anchor-driven outlier rejection (Subtotal/Payment/Rounded consistency), made rounding precedence a hard rule, strengthened header-context date ranking, and added a drop-in final validation snippet to prevent empty-string totals
- **1.1.2** (2026-10-21): Strengthened default preprocessing+PSM baseline, added explicit item-count exclusions, clarified rounding precedence as hard rule, and added explicit final output validation step
- **1.1.1** (2026-10-21): Added label-tolerant date ranking, rounding precedence, outlier rejection, strict null/2dp normalization
- **1.0.0** (2026-01-13): Initial release
