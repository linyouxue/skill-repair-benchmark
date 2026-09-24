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


## Post-OCR Structured Field Extraction

Once OCR text is available, downstream parsing (finding keyword-labelled values such
as totals, amounts, dates, or IDs) must tolerate the systematic noise Tesseract
introduces on low-quality scans: glued words (`GrandTotal`), stray punctuation
(`Grand Total.`, `GrandTotal =`), decimal glyphs recognised as `:` `;` `|` or a
space (`92:80`, `92 80`), and confusions like `O`/`0`, `l`/`1`/`I`.

A rigid regex like `r'\bGRAND\s+TOTAL\b'` or a money pattern of
`r'\d+(?:,\d{3})*\.\d{2}'` applied to the raw OCR line will silently miss the
correct answer on such images and produce spurious nulls even when the value is
visibly present across OCR variants. Use the two mechanisms below.

**Scope.** These techniques apply to post-OCR extraction from noisy scanned
documents (receipts, invoices, forms). Do **not** apply them to already-clean
text sources (PDF text layers, API JSON, structured logs, source code) or to
fields where punctuation is semantically meaningful (times `12:30`, ratios
`3:1`, IDs, version numbers).

### Keyword Location on Noisy OCR

Build a two-view representation of each line:

- **raw view** — the original line, used for value extraction.
- **normalized view** — uppercased, non-alphanumerics stripped, used only for
  keyword tier matching. `GrandTotal`, `GRAND-TOTAL`, `GRAND  TOTAL:`,
  `Grand Total.` all collapse to `GRANDTOTAL` and hit the highest-priority tier.

Encode priority keyword tiers as substring checks on the normalized view rather
than `\b`-anchored regexes on the raw line. Apply exclusion keywords
(`SUBTOTAL`, `TAX`, `GST`, `SST`, `DISCOUNT`, `CHANGE`, `CASHTENDERED`, …) on
the same normalized view so their semantics are preserved.

```python
import re

def normalize_for_keyword(line):
    """Uppercase alphanumeric-only view of a line, for tolerant keyword lookup."""
    return re.sub(r'[^A-Z0-9]', '', line.upper())

PRIORITY_TIERS = [
    ['GRANDTOTAL'],
    ['TOTALRM', 'TOTALRM'],           # 'TOTAL RM', 'TOTAL: RM' both normalize here
    ['TOTALAMOUNT'],
    ['TOTALDUE', 'AMOUNTDUE', 'BALANCEDUE',
     'NETTOTAL', 'NETTTOTAL', 'TOTAL', 'AMOUNT'],
]
EXCLUSIONS = ['SUBTOTAL', 'TAX', 'GST', 'SST',
              'DISCOUNT', 'CHANGE', 'CASHTENDERED']

def find_keyword_line(lines):
    for tier_idx, keys in enumerate(PRIORITY_TIERS):
        for raw in lines:
            norm = normalize_for_keyword(raw)
            if any(x in norm for x in EXCLUSIONS):
                continue
            if any(k in norm for k in keys):
                return tier_idx, raw
    return None, None
```

### Extracting Numeric Fields from Noisy OCR

Before concluding a keyword-hit line has no numeric value, apply an OCR-tolerant
extractor in three stages, taking the first that yields a plausible amount:

1. **Canonicalize the line.** Collapse repeated whitespace; map common OCR
   substitutions on digit/decimal glyphs (`O`→`0`, `l`/`I`→`1`,
   `:` `;` `|`→`.` **only when between digits**). Do not rewrite text globally
   — restrict substitutions to digit-adjacent positions.
2. **Match a flexible number.** Allow the fractional separator to be `.`, `,`,
   `:` or a single space, and allow thousands separators of `,` or `.`. Treat
   `,` and `.` as interchangeable when only one appears.
3. **Last-resort digit-run split.** On a line that matched a keyword tier, take
   the last run of digits (possibly with an internal space) that is 3–5 digits
   long and split off the trailing two digits as cents (e.g. `92 80` → `92.80`,
   `9280` → `92.80`). Guard with a sanity range appropriate to the field.

Only return `None` when none of these stages yields a plausible amount.

```python
MONEY_RE = re.compile(r'\d{1,3}(?:[,\. ]\d{3})*[.,:\s]\d{2}(?!\d)')

def _canonicalize(line):
    s = re.sub(r'\s+', ' ', line)
    # digit-adjacent OCR fixes only
    s = re.sub(r'(?<=\d)[:;|](?=\d)', '.', s)
    s = re.sub(r'(?<=\d)[Oo](?=\d)', '0', s)
    return s

def _to_float(tok):
    # Normalize fractional separator to '.' and drop thousands separators.
    tok = tok.strip()
    # Identify fractional separator (last of . , : or space with 2 trailing digits)
    m = re.search(r'([.,:\s])(\d{2})$', tok)
    if not m:
        return None
    sep = m.group(1)
    int_part = tok[:m.start()].replace(',', '').replace('.', '').replace(' ', '')
    frac_part = m.group(2)
    if not int_part.isdigit():
        return None
    return float(f"{int_part}.{frac_part}")

def extract_money(line, min_val=0.01, max_val=1_000_000):
    canon = _canonicalize(line)
    # Stage 2: flexible money regex
    matches = MONEY_RE.findall(canon)
    for tok in reversed(matches):  # prefer the last (rightmost) number on the line
        v = _to_float(tok)
        if v is not None and min_val <= v <= max_val:
            return v
    # Stage 3: last-resort digit-run split on the keyword-hit line
    runs = re.findall(r'\d(?:[\d ]{1,4}\d)?', canon)
    for tok in reversed(runs):
        digits = tok.replace(' ', '')
        if 3 <= len(digits) <= 7:
            v = float(f"{digits[:-2]}.{digits[-2:]}")
            if min_val <= v <= max_val:
                return v
    return None
```

### Convergence and Audit for Batch Extraction

When a batch OCR/extraction task must produce a single tabular deliverable
compared line-by-line to an oracle, treat rule iteration as bounded, not
open-ended:

1. **Freeze the schema and writeback first.** Ensure the output file (correct
   sheet name, header, ordering, null representation) is always valid on disk,
   even when some rows are `None`.
2. **Emit a per-file audit.** After each run, log for every input: the OCR
   variant used, the matched keyword tier and raw line, and every candidate
   value considered. This makes it obvious which rows are still failing and why.
3. **Only edit rules that address a named failing case.** Avoid speculative
   regex tuning; each change should reference a specific line from the audit.
4. **Set an internal edit cap.** If a small number of rows remain unrecoverable
   after a few targeted iterations, commit the current best output (with
   `None`/blank for the unrecoverable fields) rather than continuing to tune
   and risk exceeding the outer iteration budget with no file written.
5. **Prefer nulls over guesses.** If none of the OCR-tolerant stages yield a
   plausible value, leave the cell blank; do not fabricate.


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
- [ ] For structured-field extraction: keyword matching used a normalized
      (alphanumeric-only, uppercase) view of each line so glued/punctuated
      variants still hit the intended tier
- [ ] For numeric field extraction: OCR-tolerant decimal handling was applied
      before returning `None`, and the deliverable file is present and
      schema-valid on disk


## Limitations

- Tesseract works best with printed text; handwriting recognition is limited
- Accuracy decreases with decorative fonts, artistic text, or extreme stylization
- Mathematical equations and special notation may not extract accurately
- Redacted or watermarked text cannot be recovered
- Severe image degradation (blur, noise, low resolution) reduces accuracy
- Complex multi-column layouts may require custom PSM configuration


## Version History

- **1.0.0** (2026-01-13): Initial release with Tesseract/pytesseract OCR
