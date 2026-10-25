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



## Receipt Field Extraction (Date + Total)

This section is a drop-in recipe for the receipt OCR task (date + total_amount extraction). Use this directly instead of re-deriving logic.

### Output contract
- `total_amount`: two-decimal string via `f"{v:.2f}"` (e.g., `"47.70"`), or `None`.
- `date`: ISO `YYYY-MM-DD` string, or `None`.
- Produce one `results` sheet in xlsx with columns `filename, date, total_amount`, ordered by filename.

### Priority tiers and exclusions
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
    'SUBTOTAL','SUB TOTAL','SUB-TOTAL',
    'TAX','GST','SST',
    'DISCOUNT','CHANGE','CASH TENDERED','CASH RECEIVED','CASH PAYMENT',
    'VISA','MASTERCARD','DEBIT','CREDIT','CARD','PAYMENT',
    'ROUNDING ADJ','ROUNDING ADJUSTMENT',
    'TOTAL GST','TOTAL TAX','TOTAL SST','GST TOTAL','TAX TOTAL',
    'TOTAL ITEMS','TOTAL ITEM(S)','ITEM COUNT','TOTAL QTY','TOTAL QUANTITY',
    'TOTAL SAVINGS','EXCLUDING','EXCL GST','AMT EXCL',
    'DESCRIPTION','QTY PRICE AMOUNT','PRICE AMOUNT','AVERAGE','PAX',
]
```
IMPORTANT: `TOTAL GST` is excluded, but `TOTAL INCL GST` / `TOTAL (Inclusive of GST)` is NOT excluded. Check for `INCL`/`INCLUSIVE` to override the GST exclusion on that line.

### Section cutoff
Once a line matches `GST SUMMARY`, `TAX SUMMARY`, or `TAX CODE`, mark all subsequent lines as excluded for total selection.

### Amount regex (strict two-decimal, thousands-separator aware)
```python
AMOUNT_RE = re.compile(r'(?<![\w.])(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})(?![\w.\d])')

def to_float(tok):
    return float(tok.replace(',', ''))
```

### OCR normalization (apply inside numeric-looking tokens only)
- `O/o/Q → 0`, `l/I/| → 1`, `S → 5`, `B → 8`, `u → 0`
- Standalone `RN` → `RM`
- `':'` → `'.'` inside amount tokens (e.g., `23:25` → `23.25`)
- Collapse `NN NN` at end of a keyword line into `NN.NN`

### Preprocessing variants (use ALL of these)
```python
from PIL import Image, ImageOps

def variants(path):
    img = Image.open(path)
    gray = ImageOps.autocontrast(img.convert('L'))
    w, h = gray.size
    up2 = gray.resize((w*2, h*2), Image.LANCZOS)
    up3 = gray.resize((w*3, h*3), Image.LANCZOS)
    binz = gray.point(lambda p: 255 if p > 150 else 0)
    return [
        (img, '--psm 6'),
        (gray, '--psm 6'),
        (up2, '--psm 6'),
        (up3, '--psm 4'),
        (gray, '--psm 11'),
        (binz, '--psm 6'),
    ]
```

### Selection algorithm (per variant)
For each line:
1. Uppercase a copy for keyword matching.
2. If section cutoff triggered, skip.
3. If any EXCLUSION keyword matches AND it is not overridden by `INCL`/`INCLUSIVE`, skip for selection.
4. For each tier (lowest index = highest priority), if a tier keyword matches:
   - Find all AMOUNT_RE matches on this line; if any, take the LAST one as candidate at `(tier_idx, value, line_no)`.
   - If the line has NO digits at all (truly split), look ahead up to 2 non-empty, non-excluded lines; take the LAST 2-decimal number there.
   - If the line has partial/garbled digits but no valid 2-decimal match, do NOT fall through (prevents Visa/Cash leakage).

### Final cross-variant selection
1. Aggregate candidates from all variants.
2. Pick the LOWEST `tier_idx` with any candidate.
3. Within that tier, prefer values corroborated by Subtotal/Payment/Cash/Rounded Total lines on the receipt, or appearing in multiple variants.
4. Tie-break by cross-variant frequency, then by LAST occurrence in receipt order (final rounded total wins over earlier `Total (Inclusive of GST)`).

Worked example: a receipt containing
```
Total (Inclusive of GST): 23.26
Rounding Adj: -0.01
TOTAL: 23.25
```
Both 23.26 and 23.25 are tier-3 candidates. The later `TOTAL: 23.25` wins (last-occurrence rule), yielding `"23.25"`.

### Date extraction
```python
import re
MONTHS = {m:i+1 for i,m in enumerate(['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'])}

DATE_PATTERNS = [
    (re.compile(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})'), 'dmy'),
    (re.compile(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})'), 'ymd'),
    (re.compile(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})(?!\d)'), 'dmy2'),
    (re.compile(r'(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{2,4})'), 'dmony'),
]

def validate(y, mo, d):
    try:
        if not (2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31):
            return None
        return f"{y:04d}-{mo:02d}-{d:02d}"
    except Exception:
        return None

def try_swaps(y, mo, d):
    # single-digit confusion swaps on month then day
    swaps = {'6':'0','0':'6','8':'3','3':'8','1':'7','7':'1','5':'6','6':'5'}
    for field in ('mo','d'):
        v = mo if field=='mo' else d
        s = str(v)
        for i,ch in enumerate(s):
            if ch in swaps:
                new = int(s[:i]+swaps[ch]+s[i+1:])
                ny, nmo, nd = (y, new, d) if field=='mo' else (y, mo, new)
                r = validate(ny, nmo, nd)
                if r: return r
    return None

def parse_date_line(line):
    label_boost = any(k in line.upper() for k in ('DATE','TARIKH','INV'))
    for pat, kind in DATE_PATTERNS:
        for m in pat.finditer(line):
            if kind == 'ymd':
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif kind == 'dmy':
                a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                # Malaysian/SEA default DD/MM unless a>12 forces MM/DD
                if a > 12 and b <= 12:
                    d, mo = b, a  # was MM/DD
                else:
                    d, mo = a, b
            elif kind == 'dmy2':
                a, b, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
                y = 2000 + yy if yy <= 49 else 1900 + yy
                if a > 12 and b <= 12:
                    d, mo = b, a
                else:
                    d, mo = a, b
            elif kind == 'dmony':
                d = int(m.group(1))
                mo = MONTHS.get(m.group(2)[:3].upper(), 0)
                yy = int(m.group(3))
                y = yy if yy >= 100 else (2000+yy if yy<=49 else 1900+yy)
            r = validate(y, mo, d) or try_swaps(y, mo, d)
            if r:
                return r, label_boost
    return None, False
```
Scan all lines across variants; prefer a date on a label-boosted line; otherwise take the first validated date.

### Reference function
```python
import pytesseract

def extract_receipt_fields(image_path):
    texts = []
    for im, cfg in variants(image_path):
        try:
            texts.append(pytesseract.image_to_string(im, config=cfg))
        except Exception:
            pass
    # ... run selection algorithm on each `texts[i]`, aggregate candidates,
    # pick final total per rules above; scan lines for date.
    return {'date': date_or_none, 'total_amount': (f"{v:.2f}" if v is not None else None)}
```

### Batch driver
```python
import os, glob
import openpyxl

def run(img_dir='/app/workspace/dataset/img', out='/app/workspace/stat_ocr.xlsx'):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'results'
    ws.append(['filename','date','total_amount'])
    for p in sorted(glob.glob(os.path.join(img_dir, '*.jpg'))):
        fn = os.path.basename(p)
        r = extract_receipt_fields(p)
        ws.append([fn, r['date'], r['total_amount']])
    wb.save(out)
```
