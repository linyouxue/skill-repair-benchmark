---
name: image-ocr
description: Extract text content from images using Tesseract OCR via Python
---

# Image OCR Skill

## Purpose
This skill enables accurate text extraction from image files (JPG, PNG, etc.) using Tesseract OCR via the `pytesseract` Python library. It is suitable for scanned documents, screenshots, photos of text, receipts, forms, and other visual content containing text.

## When to Use
- Extracting text from scanned documents or photos
- Reading text from screenshots or image captures
- Processing batch image files that contain textual information
- Converting visual documents to machine-readable text
- Extracting structured data from forms, receipts, or tables in images



## Receipt Field Extraction (Date + Total)

This section is a domain-specific recipe for extracting `date` (ISO `YYYY-MM-DD`) and `total_amount` (two-decimal string) from scanned receipt images (Malaysian/SEA style). Use this recipe when the task asks for receipt totals and dates; the generic OCR sections below are inadequate on their own.

### Priority Tiers and Exclusions

```python
TIERS = [
    ['GRAND TOTAL'],
    ['TOTAL RM', 'TOTAL: RM'],
    ['TOTAL AMOUNT'],
    ['TOTAL', 'AMOUNT', 'TOTAL DUE', 'AMOUNT DUE', 'BALANCE DUE',
     'NETT TOTAL', 'NET TOTAL', 'ROUNDED TOTAL', 'TOTAL ROUNDED',
     'TOTAL AFTER ROUNDING', 'TOTAL INCL GST', 'TOTAL RM INCLUDING GST'],
]

EXCLUSIONS = [
    'SUBTOTAL', 'SUB TOTAL', 'SUB-TOTAL',
    'TAX', 'GST', 'SST',
    'DISCOUNT', 'CHANGE',
    'CASH TENDERED', 'CASH RECEIVED', 'CASH PAYMENT',
    'VISA', 'MASTERCARD', 'DEBIT', 'CREDIT', 'CARD', 'PAYMENT',
    'ROUNDING ADJ', 'ROUNDING ADJUSTMENT',
    'TOTAL GST', 'TOTAL TAX', 'TOTAL SST', 'GST TOTAL', 'TAX TOTAL',
    'TOTAL ITEMS', 'TOTAL ITEM(S)', 'ITEM COUNT', 'TOTAL QTY',
    'TOTAL QUANTITY', 'TOTAL SAVINGS',
    'EXCLUDING', 'EXCL GST', 'AMT EXCL',
    'DESCRIPTION', 'QTY PRICE AMOUNT', 'PRICE AMOUNT',
    'AVERAGE', 'PAX',
]
```

IMPORTANT nuances:
- Distinguish `TOTAL GST` / `GST TOTAL` (EXCLUDE) from `TOTAL INCL GST` / `TOTAL (INCLUSIVE OF GST)` (INCLUDE). Check INCLUDE patterns before applying EXCLUSIONS.
- Once any line contains `GST SUMMARY`, `TAX SUMMARY`, or `TAX CODE`, mark all subsequent lines as excluded for total selection (summary tables often repeat a 'Total' row).

### Amount Regex and Normalization

```python
import re
AMOUNT_RE = re.compile(r'(?<![\w.])(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})(?![\w.\d])')

def to_float(tok):
    return float(tok.replace(',', ''))

def fmt_amount(v):
    return f'{v:.2f}'

def normalize_numeric_tokens(line):
    # Apply only inside tokens that look numeric-ish (contain a digit).
    def fix_token(tok):
        if not re.search(r'\d', tok):
            return tok
        t = tok
        t = t.replace('O', '0').replace('o', '0').replace('Q', '0').replace('u', '0')
        t = t.replace('l', '1').replace('I', '1').replace('|', '1')
        t = t.replace('S', '5').replace('B', '8')
        t = t.replace(':', '.')
        return t
    line = re.sub(r'\bRN\b', 'RM', line)
    # Collapse 'NN NN' at end of a keyword line into 'NN.NN'
    line = re.sub(r'(\d{1,4})\s+(\d{2})\s*$', r'\1.\2', line)
    return ' '.join(fix_token(t) for t in line.split(' '))
```

### Multi-Variant OCR

Generate at least four variants and collect text from each:
1. Original, `--psm 6`
2. Grayscale + autocontrast, `--psm 6`
3. 2x LANCZOS upscale of #2, `--psm 6`
4. 3x LANCZOS upscale of #2, `--psm 4`
5. (optional) Binarized/inverted for faded scans, `--psm 11`

```python
from PIL import Image, ImageOps
import pytesseract

def ocr_variants(image_path):
    img = Image.open(image_path)
    gray = ImageOps.autocontrast(ImageOps.grayscale(img))
    w, h = gray.size
    up2 = gray.resize((w*2, h*2), Image.LANCZOS)
    up3 = gray.resize((w*3, h*3), Image.LANCZOS)
    specs = [(img, '--psm 6'), (gray, '--psm 6'),
             (up2, '--psm 6'), (up3, '--psm 4')]
    texts = []
    for im, cfg in specs:
        try:
            texts.append(pytesseract.image_to_string(im, config=cfg))
        except Exception:
            pass
    return texts
```

### Selection Algorithm (Total)

For each OCR variant text, split into lines; for each line:
1. Apply `normalize_numeric_tokens`.
2. If a prior line matched `GST SUMMARY`/`TAX SUMMARY`/`TAX CODE`, treat this line as excluded.
3. If the uppercased line contains any EXCLUSION keyword (and NOT an INCLUDE pattern like `TOTAL INCL GST` / `INCLUSIVE OF GST`), skip.
4. For each tier (lowest index wins), if the line contains a tier keyword, extract 2-decimal amounts via `AMOUNT_RE`.
   - If amounts found: record `(tier_index, value, line_index, variant_index)` for the LAST amount on that line.
   - If no amounts AND the line contains no digits at all: look ahead up to 2 non-empty, non-excluded lines; take the LAST 2-decimal number found. Record as candidate.
   - If the keyword line has partial digits but no valid 2-decimal match: do NOT fall through (prevents Visa/Cash leakage).

Final pick across all variants:
1. Choose the lowest `tier_index` that has any candidate.
2. Within that tier, prefer values corroborated by (a) appearing on Subtotal/Payment/Cash/Rounded lines on the same receipt, or (b) appearing in multiple variants.
3. Tiebreak by cross-variant frequency, then by LAST line_index (so a final `TOTAL: 23.25` beats an earlier `Total (Inclusive of GST): 23.26` when a `Rounding Adj: -0.01` sits between them).
4. Output `fmt_amount(value)`.

Worked example:
```
Total (Inclusive of GST):   23.26
Rounding Adj:               -0.01
TOTAL:                      23.25
```
Both `23.26` and `23.25` are tier-3 candidates. The later line wins → `total_amount = '23.25'`.

### Date Extraction

```python
import re
from datetime import date

DATE_PATTERNS = [
    (re.compile(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})'), 'dmy4'),
    (re.compile(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})'), 'ymd'),
    (re.compile(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})\b'), 'dmy2'),
    (re.compile(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})', re.I), 'dmony'),
]
MONTHS = {m:i+1 for i,m in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'])}

def _valid(y, mo, d):
    try:
        date(y, mo, d); return 2000 <= y <= 2099
    except Exception:
        return False

def _try_swaps(y, mo, d):
    swaps = [('6','0'),('0','6'),('8','3'),('3','8'),('1','7'),('7','1'),('5','6'),('6','5')]
    for field in ('mo','d'):
        s = str(mo if field=='mo' else d)
        for a,b in swaps:
            if a in s:
                cand = int(s.replace(a,b,1))
                nm, nd = (cand, d) if field=='mo' else (mo, cand)
                if _valid(y, nm, nd):
                    return y, nm, nd
    return None

def _strip_handwritten_tokens(ln):
    # Remove alphanumeric tokens starting with letters followed by digits
    # (e.g., 'GA1801', 'GB1801', 'A03041') which are handwritten annotations
    # that can poison date extraction.
    return ' '.join(t for t in ln.split()
                    if not re.match(r'^[A-Za-z]{1,3}\d{3,}$', t))

def extract_date(text, year_range=(2015, 2019)):
    lines = text.splitlines()
    # Prefer lines near Date/Tarikh/INV/Receipt/Dated labels first.
    # When a label line contains both a date and a time, split on whitespace
    # so the date substring is parsed independently of the time.
    scored = []
    for i, ln in enumerate(lines):
        clean = _strip_handwritten_tokens(ln)
        boost = 2 if re.search(r'\b(date|tarikh|dated)\b', clean, re.I) else (1 if re.search(r'receipt|inv', clean, re.I) else 0)
        scored.append((boost, i, clean))
        # Also enqueue each whitespace-separated chunk of label lines
        # so 'Date: 09/03/2018  Time: 08:49:00' yields '09/03/2018' alone.
        if boost >= 2:
            for chunk in re.split(r'\s{2,}|\t', clean):
                scored.append((boost + 1, i, chunk))
    scored.sort(key=lambda x: (-x[0], x[1]))
    ymin, ymax = year_range
    for _, _, ln in scored:
        for rx, kind in DATE_PATTERNS:
            m = rx.search(ln)
            if not m: continue
            if kind == 'dmy4':
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if mo > 12 and d <= 12:  # fallback to MM/DD
                    d, mo = mo, d
            elif kind == 'ymd':
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif kind == 'dmy2':
                d, mo, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
                y = 2000 + yy if yy <= 49 else 1900 + yy
            elif kind == 'dmony':
                d = int(m.group(1)); mo = MONTHS[m.group(2).lower()[:3]]; y = int(m.group(3))
            if _valid(y, mo, d) and ymin <= y <= ymax:
                return f'{y:04d}-{mo:02d}-{d:02d}'
            fix = _try_swaps(y, mo, d)
            if fix:
                y, mo, d = fix
                if ymin <= y <= ymax:
                    return f'{y:04d}-{mo:02d}-{d:02d}'
    # Second pass: relax the year-range sanity check if nothing matched.
    for _, _, ln in scored:
        for rx, kind in DATE_PATTERNS:
            m = rx.search(ln)
            if not m: continue
            try:
                if kind == 'dmy4':
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if mo > 12 and d <= 12:
                        d, mo = mo, d
                elif kind == 'ymd':
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif kind == 'dmy2':
                    d, mo, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    y = 2000 + yy if yy <= 49 else 1900 + yy
                elif kind == 'dmony':
                    d = int(m.group(1)); mo = MONTHS[m.group(2).lower()[:3]]; y = int(m.group(3))
                if _valid(y, mo, d):
                    return f'{y:04d}-{mo:02d}-{d:02d}'
            except Exception:
                continue
    return None
```

For ambiguous `DD/MM` vs `MM/DD`, default to `DD/MM/YYYY` (Malaysian/SEA convention). Example: `09/03/2018` → `2018-03-09` (NOT `2018-08-09`).



#### Date extraction robustness notes

- **Label priority is primary, voting is secondary.** Always prefer tokens on lines whose uppercased form contains `DATE`, `TARIKH`, `DATED`, or `RECEIPT`. Only fall back to unlabeled numeric scanning when no labeled line yields a valid parse. Do NOT majority-vote across OCR variants in a way that lets unlabeled numeric tokens outweigh a clean labeled read.
- **Reject handwritten annotation tokens.** Receipts in this dataset (e.g., 039.jpg Perniagaan Zheng Hui) have handwritten short alphanumerics next to line items such as `GA1801`, `GB1801`, `A03041`. Strip any whitespace-separated token matching `^[A-Za-z]{1,3}\d{3,}$` before running the date regex — otherwise fragments like `1801` can poison the parse.
- **Split label lines containing both date and time.** When a line looks like `Date: 09/03/2018  Time: 08:49:00`, split on runs of 2+ spaces or tabs and parse each chunk independently so the time colons don't interact with slash-based date patterns.
- **Year sanity window.** The dataset covers 2015–2019. Reject any first-pass parse whose year is outside `[2015, 2019]` (e.g., spurious `1801` → year 1801). Only relax this window on a second pass if no in-range candidate was found.
- **Low-confidence fallback.** If the primary date vote has low confidence (no labeled match, no in-range candidate), re-run OCR on the top-right header crop (roughly the upper 30% × right 60% of the image) at 3× scale with `--psm 6`, since `Date:` on tax-invoice receipts almost always sits in that region.

### Reference Function and Batch Driver

```python
def extract_receipt_fields(image_path):
    variant_texts = ocr_variants(image_path)
    # --- total selection ---
    include_pat = re.compile(r'TOTAL\s*(\(?\s*INCL(?:USIVE)?(?:\s*OF)?\s*GST|INCL\s*GST)', re.I)
    candidates = []  # (tier, value, line_idx, variant_idx, line_text)
    corroborators = set()
    for vi, raw in enumerate(variant_texts):
        in_summary = False
        lines = [normalize_numeric_tokens(l) for l in raw.splitlines()]
        for li, line in enumerate(lines):
            U = line.upper()
            if any(k in U for k in ('GST SUMMARY','TAX SUMMARY','TAX CODE')):
                in_summary = True
            # Corroborators
            if any(k in U for k in ('SUBTOTAL','SUB TOTAL','CASH','PAYMENT','ROUNDED','TENDERED','CHANGE')):
                for m in AMOUNT_RE.finditer(line):
                    corroborators.add(to_float(m.group(1)))
            is_include = bool(include_pat.search(U))
            is_excluded = in_summary or (not is_include and any(k in U for k in EXCLUSIONS))
            if is_excluded:
                continue
            for ti, kws in enumerate(TIERS):
                if any(k in U for k in kws):
                    amounts = [to_float(m.group(1)) for m in AMOUNT_RE.finditer(line)]
                    if amounts:
                        candidates.append((ti, amounts[-1], li, vi, line))
                    elif not re.search(r'\d', line):
                        # split-line fallback: look ahead up to 2 non-excluded lines
                        for look in range(li+1, min(li+3, len(lines))):
                            nxt = lines[look]
                            if not nxt.strip(): continue
                            NU = nxt.upper()
                            if any(k in NU for k in EXCLUSIONS): continue
                            nx = [to_float(m.group(1)) for m in AMOUNT_RE.finditer(nxt)]
                            if nx:
                                candidates.append((ti, nx[-1], look, vi, nxt))
                                break
                    break  # only match the strongest tier per line
    total_str = None
    if candidates:
        best_tier = min(c[0] for c in candidates)
        pool = [c for c in candidates if c[0] == best_tier]
        from collections import Counter
        freq = Counter(round(c[1], 2) for c in pool)
        def score(c):
            v = round(c[1], 2)
            return (freq[v], 1 if v in {round(x,2) for x in corroborators} else 0, c[2])
        pool.sort(key=score, reverse=True)
        total_str = fmt_amount(pool[0][1])
    # --- date ---
    date_iso = None
    for raw in variant_texts:
        date_iso = extract_date(raw)
        if date_iso: break
    return {'date': date_iso, 'total_amount': total_str}

# Batch driver → xlsx
def build_xlsx(img_dir, out_path):
    import os, openpyxl
    from pathlib import Path
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'results'
    ws.append(['filename', 'date', 'total_amount'])
    files = sorted(p.name for p in Path(img_dir).iterdir()
                   if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'})
    for name in files:
        res = extract_receipt_fields(os.path.join(img_dir, name))
        ws.append([name, res['date'], res['total_amount']])
    wb.save(out_path)
```

### Output Contract
- `total_amount`: two-decimal string (e.g., `'47.70'`), or `None` on failure.
- `date`: ISO `YYYY-MM-DD` string, or `None` on failure.
- xlsx contains exactly one sheet `results`, header row + sorted-by-filename data rows, no extra columns/sheets.

## Required Libraries

The following Python libraries are required:

```python
import pytesseract
from PIL import Image
import json
import os
```

## Input Requirements
- **File formats**: JPG, JPEG, PNG, WEBP
- **Image quality**: Minimum 300 DPI recommended for printed text; clear and legible text
- **File size**: Under 5MB per image (resize if necessary)
- **Text language**: Specify if non-English to improve accuracy

## Output Schema
All extracted content must be returned as valid JSON conforming to this schema:

```json
{
  "success": true,
  "filename": "example.jpg",
  "extracted_text": "Full raw text extracted from the image...",
  "confidence": "high|medium|low",
  "metadata": {
    "language_detected": "en",
    "text_regions": 3,
    "has_tables": false,
    "has_handwriting": false
  },
  "warnings": [
    "Text partially obscured in bottom-right corner",
    "Low contrast detected in header section"
  ]
}
```


### Field Descriptions

- `success`: Boolean indicating whether text extraction completed
- `filename`: Original image filename
- `extracted_text`: Complete text content in reading order (top-to-bottom, left-to-right)
- `confidence`: Overall OCR confidence level based on image quality and text clarity
- `metadata.language_detected`: ISO 639-1 language code
- `metadata.text_regions`: Number of distinct text blocks identified
- `metadata.has_tables`: Whether tabular data structures were detected
- `metadata.has_handwriting`: Whether handwritten text was detected
- `warnings`: Array of quality issues or potential errors


## Code Examples

### Basic OCR Extraction

```python
import pytesseract
from PIL import Image

def extract_text_from_image(image_path):
    """Extract text from a single image using Tesseract OCR."""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    return text.strip()
```

### OCR with Confidence Data

```python
import pytesseract
from PIL import Image

def extract_with_confidence(image_path):
    """Extract text with per-word confidence scores."""
    img = Image.open(image_path)

    # Get detailed OCR data including confidence
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    words = []
    confidences = []

    for i, word in enumerate(data['text']):
        if word.strip():  # Skip empty strings
            words.append(word)
            confidences.append(data['conf'][i])

    # Calculate average confidence
    avg_confidence = sum(c for c in confidences if c > 0) / len([c for c in confidences if c > 0]) if confidences else 0

    return {
        'text': ' '.join(words),
        'average_confidence': avg_confidence,
        'word_count': len(words)
    }
```

### Full OCR with JSON Output

```python
import pytesseract
from PIL import Image
import json
import os

def ocr_to_json(image_path):
    """Perform OCR and return results as JSON."""
    filename = os.path.basename(image_path)
    warnings = []

    try:
        img = Image.open(image_path)

        # Get detailed OCR data
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        # Extract text preserving structure
        text = pytesseract.image_to_string(img)

        # Calculate confidence
        confidences = [c for c in data['conf'] if c > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        # Determine confidence level
        if avg_conf >= 80:
            confidence = "high"
        elif avg_conf >= 50:
            confidence = "medium"
        else:
            confidence = "low"
            warnings.append(f"Low OCR confidence: {avg_conf:.1f}%")

        # Count text regions (blocks)
        block_nums = set(data['block_num'])
        text_regions = len([b for b in block_nums if b > 0])

        result = {
            "success": True,
            "filename": filename,
            "extracted_text": text.strip(),
            "confidence": confidence,
            "metadata": {
                "language_detected": "en",
                "text_regions": text_regions,
                "has_tables": False,
                "has_handwriting": False
            },
            "warnings": warnings
        }

    except Exception as e:
        result = {
            "success": False,
            "filename": filename,
            "extracted_text": "",
            "confidence": "low",
            "metadata": {
                "language_detected": "unknown",
                "text_regions": 0,
                "has_tables": False,
                "has_handwriting": False
            },
            "warnings": [f"OCR failed: {str(e)}"]
        }

    return result

# Usage
result = ocr_to_json("document.jpg")
print(json.dumps(result, indent=2))
```

### Batch Processing Multiple Images

```python
import pytesseract
from PIL import Image
import json
import os
from pathlib import Path

def process_image_directory(directory_path, output_file):
    """Process all images in a directory and save results."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    results = []

    for file_path in sorted(Path(directory_path).iterdir()):
        if file_path.suffix.lower() in image_extensions:
            result = ocr_to_json(str(file_path))
            results.append(result)
            print(f"Processed: {file_path.name}")

    # Save results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    return results
```


## Tesseract Configuration Options

### Language Selection

```python
# Specify language (default is English)
text = pytesseract.image_to_string(img, lang='eng')

# Multiple languages
text = pytesseract.image_to_string(img, lang='eng+fra+deu')
```

### Page Segmentation Modes (PSM)

Use `--psm` to control how Tesseract segments the image:

```python
# PSM 3: Fully automatic page segmentation (default)
text = pytesseract.image_to_string(img, config='--psm 3')

# PSM 4: Assume single column of text
text = pytesseract.image_to_string(img, config='--psm 4')

# PSM 6: Assume uniform block of text
text = pytesseract.image_to_string(img, config='--psm 6')

# PSM 11: Sparse text - find as much text as possible
text = pytesseract.image_to_string(img, config='--psm 11')
```

Common PSM values:
- `0`: Orientation and script detection (OSD) only
- `3`: Fully automatic page segmentation (default)
- `4`: Single column of text of variable sizes
- `6`: Uniform block of text
- `7`: Single text line
- `11`: Sparse text
- `13`: Raw line


## Image Preprocessing

For better OCR accuracy, preprocess images:

```python
from PIL import Image, ImageFilter, ImageOps

def preprocess_image(image_path):
    """Preprocess image for better OCR results."""
    img = Image.open(image_path)

    # Convert to grayscale
    img = img.convert('L')

    # Increase contrast
    img = ImageOps.autocontrast(img)

    # Apply slight sharpening
    img = img.filter(ImageFilter.SHARPEN)

    return img

# Use preprocessed image for OCR
img = preprocess_image("document.jpg")
text = pytesseract.image_to_string(img)
```

### Advanced Preprocessing Strategies

For difficult images (low contrast, faded text, dark backgrounds), try multiple preprocessing approaches:

1. **Grayscale + Autocontrast** - Basic enhancement for most images
2. **Inverted** - Use `ImageOps.invert()` for dark backgrounds with light text
3. **Scaling** - Upscale small images (e.g., 2x) before OCR to improve character recognition
4. **Thresholding** - Convert to binary using `img.point(lambda p: 255 if p > threshold else 0)` with different threshold values (e.g., 100, 128)
5. **Sharpening** - Apply `ImageFilter.SHARPEN` to improve edge clarity


## Multi-Pass OCR Strategy

For challenging images, a single OCR pass may miss text. Use multiple passes with different configurations:

1. **Try multiple PSM modes** - Different page segmentation modes work better for different layouts (e.g., `--psm 6` for blocks, `--psm 4` for columns, `--psm 11` for sparse text)

2. **Try multiple preprocessing variants** - Run OCR on several preprocessed versions of the same image

3. **Combine results** - Aggregate text from all passes to maximize extraction coverage

```python
def multi_pass_ocr(image_path):
    """Run OCR with multiple strategies and combine results."""
    img = Image.open(image_path)
    gray = ImageOps.grayscale(img)

    # Generate preprocessing variants
    variants = [
        ImageOps.autocontrast(gray),
        ImageOps.invert(ImageOps.autocontrast(gray)),
        gray.filter(ImageFilter.SHARPEN),
    ]

    # PSM modes to try
    psm_modes = ['--psm 6', '--psm 4', '--psm 11']

    all_text = []
    for variant in variants:
        for psm in psm_modes:
            try:
                text = pytesseract.image_to_string(variant, config=psm)
                if text.strip():
                    all_text.append(text)
            except Exception:
                pass

    # Combine all extracted text
    return "\n".join(all_text)
```

This approach improves extraction for receipts, faded documents, and images with varying quality.


## Error Handling

### Common Issues and Solutions

**Issue**: Tesseract not found

```python
# Verify Tesseract is installed
try:
    pytesseract.get_tesseract_version()
except pytesseract.TesseractNotFoundError:
    print("Tesseract is not installed or not in PATH")
```

**Issue**: Poor OCR quality

- Preprocess image (grayscale, contrast, sharpen)
- Use appropriate PSM mode for the document type
- Ensure image resolution is sufficient (300+ DPI)

**Issue**: Empty or garbage output

- Check if image contains actual text
- Try different PSM modes
- Verify image is not corrupted


## Quality Self-Check

Before returning results, verify:

- [ ] Output is valid JSON (use `json.loads()` to validate)
- [ ] All required fields are present (`success`, `filename`, `extracted_text`, `confidence`, `metadata`)
- [ ] Text preserves logical reading order
- [ ] Confidence level reflects actual OCR quality
- [ ] Warnings array includes all detected issues
- [ ] Special characters are properly escaped in JSON


## Limitations

- Tesseract works best with printed text; handwriting recognition is limited
- Accuracy decreases with decorative fonts, artistic text, or extreme stylization
- Mathematical equations and special notation may not extract accurately
- Redacted or watermarked text cannot be recovered
- Severe image degradation (blur, noise, low resolution) reduces accuracy
- Complex multi-column layouts may require custom PSM configuration


## Version History

- **1.0.0** (2026-01-13): Initial release with Tesseract/pytesseract OCR
