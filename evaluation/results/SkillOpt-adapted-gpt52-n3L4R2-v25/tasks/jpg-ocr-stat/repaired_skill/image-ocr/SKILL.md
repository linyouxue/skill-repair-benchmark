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

### Receipt OCR Primitive

```python
import pytesseract
from PIL import Image, ImageOps, ImageFilter

def receipt_ocr_lines(image_path):
    """Return receipt OCR as line-preserving text, using several robust passes."""
    source = Image.open(image_path).convert("L")
    scale = 2 if max(source.size) < 2500 else 1
    if scale != 1:
        source = source.resize((source.width * scale, source.height * scale))
    gray = ImageOps.autocontrast(source).filter(ImageFilter.SHARPEN)
    variants = [gray]
    variants.append(gray.point(lambda p: 255 if p >= 160 else 0))
    variants.append(gray.point(lambda p: 255 if p >= 200 else 0))

    candidates = []
    for image in variants:
        for config in ("--psm 4", "--psm 6", "--psm 11"):
            text = pytesseract.image_to_string(image, lang="eng", config=config)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines:
                candidates.append(lines)
    # Prefer the longest plausible line-preserving result; never join lines before parsing.
    return max(candidates, key=lambda lines: (len(lines), sum(map(len, lines))), default=[])
```

For receipt work, parse the returned list of lines rather than a whitespace-collapsed OCR string. Keep the date and total results as separate variables so failure of one field does not null the other.

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

def process_receipt_directory(directory_path):
    """Enumerate receipt images deterministically and return one parsed record per image."""
    image_extensions = {'.jpg', '.jpeg', '.png'}
    paths = sorted(
        (path for path in Path(directory_path).rglob('*')
         if path.is_file() and path.suffix.lower() in image_extensions),
        key=lambda path: (path.name, str(path))
    )
    records = []
    for path in paths:
        lines = receipt_ocr_lines(str(path))
        # parse_receipt_fields must independently return {"date": ..., "total_amount": ...}.
        fields = parse_receipt_fields(lines)
        records.append({
            "filename": path.name,
            "date": fields.get("date"),
            "total_amount": fields.get("total_amount")
        })
    return records

# The spreadsheet writer must use these records in this order; do not add OCR text,
# confidence fields, summaries, helper rows, or duplicate records.
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



### Deterministic Receipt Parsing Rules

Use Pillow preprocessing before OCR: grayscale, autocontrast, mild sharpening, 2x upscaling for small receipts, and at least one thresholded variant. Run receipt-friendly Tesseract modes such as `--psm 4`, `--psm 6`, and `--psm 11`, then retain line boundaries from `splitlines()`.

Extract dates independently from totals. Accept plausible numeric forms such as `DD/MM/YYYY`, `DD-MM-YYYY`, `YYYY/MM/DD`, and `YYYY-MM-DD`, plus unambiguous month-name forms. Only in a date candidate may obvious OCR substitutions such as `O`/`o` to `0` and `I`/`l`/`|` to `1` be corrected. Calendar-validate the candidate, normalize it to `YYYY-MM-DD`, and return null when absent, invalid, or ambiguous; never guess day/month order.

For totals, inspect non-excluded lines by this priority: `GRAND TOTAL`; `TOTAL RM` or `TOTAL: RM`; `TOTAL AMOUNT`; then `TOTAL`, `AMOUNT`, `TOTAL DUE`, `AMOUNT DUE`, `BALANCE DUE`, `NETT TOTAL`, and `NET TOTAL`. Skip any line containing `SUBTOTAL`, `SUB TOTAL`, `TAX`, `GST`, `SST`, `DISCOUNT`, `CHANGE`, or `CASH TENDERED`, case-insensitively. From the selected line use the last valid monetary number. Accept grouping commas and remove them before numeric conversion. If a selected keyword line has no amount, use the last valid number on the next nonempty line. Correct `O`/`o` to `0` and `I`/`l`/`|` to `1` only within numeric candidates. Format a successful total with exactly two decimal places; otherwise return null.

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



### Receipt Spreadsheet Contract

For the receipt extraction task, create or overwrite `/app/workspace/stat_ocr.xlsx` with exactly one worksheet named `results`. The first row must be exactly `filename`, `date`, `total_amount`, with no extra columns, rows, sheets, formulas, indexes, summaries, or helper content. Write one data row per supplied JPG/JPEG/PNG image, ordered lexicographically by filename. Store dates as ISO strings `YYYY-MM-DD`, totals as strings with exactly two decimal places (including trailing zeroes), and use null/blank cell values independently when date or total extraction fails. Reopen the saved workbook and verify the sheet name, dimensions, headers, row order, exact values, and absence of extra content.

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
