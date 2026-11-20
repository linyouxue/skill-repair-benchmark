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

### Bundled multi-variant runner (`scripts/receipt_ocr.py`)

Instead of hand-rolling this loop, use the bundled helper. It provides:

- A small, labelled set of `Variant` presets (`DEFAULT_VARIANTS`) that cover
  most printed receipts, and a wider `ALL_VARIANTS` set for stubborn images.
- Deterministic preprocessing (grayscale + autocontrast, optional sharpen /
  invert, upscaling at 2x or 3x).
- An on-disk cache keyed by the image's SHA-1, so re-running extraction after
  tweaking downstream regexes does NOT re-pay the OCR cost.

```python
from skills.image_ocr.scripts.receipt_ocr import (
    ocr_variants, DEFAULT_VARIANTS, ALL_VARIANTS, iter_images,
)

for path in iter_images("/path/to/images"):
    texts = ocr_variants(path, variants=DEFAULT_VARIANTS, cache_dir="/tmp/ocr_cache")
    # texts == [(raw_text, variant_label), ...]
```

Guidelines:

- **Start with `DEFAULT_VARIANTS` for every image.** Only widen to
  `ALL_VARIANTS` for the handful of images that still extract nothing.
- **Always pass `cache_dir=`** when running a batch; the cache is a lifesaver
  when you iterate on extraction logic.
- For a quick inspection use ``python scripts/receipt_ocr.py IMAGE --psm 6
  --upscale 2`` and pipe to ``less``.


## Scanned-receipt / invoice extraction pattern

When OCR is a means to pulling a few structured fields (date, amount,
invoice number, etc.) out of many scanned documents, follow this workflow
rather than reinventing it:

### 1. Produce the raw text once (and cache it)

Use `receipt_ocr.ocr_variants` with `cache_dir=...` so each image is OCR'd
at most once per variant across the whole session.

### 2. Reuse the bundled field helpers (`scripts/field_extraction.py`)

These helpers are generic — they take the keyword table as an argument so
the Skill does not assume any particular domain vocabulary:

- `find_money_values(line)` / `last_money_value(line)` — robust decimal
  parsing. Handles `1,234.56`, `12,34` (European), and skips noise.
- `parse_date_candidates(text, day_first=True)` — returns all parseable
  dates as ISO strings. Choose `day_first` to match the document locale.
- `pick_best_date(candidates)` — mode-voting over the dates found across
  OCR variants.
- `extract_by_priority(text, tiers, exclusion_patterns=..., section_break_patterns=...)`
  — the standard "priority keyword tier" lookup used on receipts/invoices:
  * Tiers are tried from most specific to least specific.
  * Within a tier the last matching line wins (final totals come last).
  * Lines matched by `exclusion_patterns` are skipped entirely.
  * `section_break_patterns` cut off everything below a header such as a
    tax summary table.
  * When a keyword appears on a line by itself, the next non-excluded
    line is used as a fallback — but a line with corrupted digits does
    NOT trigger the fallback (prevents picking up the wrong "RM 688.17"
    style payment line).
- `vote_candidates([candidates_from_each_variant])` — pick the best
  candidate across OCR variants, preferring the most specific tier and
  then the most common value.

The caller is responsible for supplying the task-specific keyword lists,
exclusions and section-break headers. A sketch:

```python
from skills.image_ocr.scripts.field_extraction import (
    KeywordTier, extract_by_priority, parse_date_candidates,
    pick_best_date, vote_candidates, format_money,
)

TIERS = [
    KeywordTier("most_specific", (r"\b<SPECIFIC-PHRASE>\b",)),
    KeywordTier("specific",      (r"\b<LESS-SPECIFIC>\b",)),
    KeywordTier("generic",       (r"\b<FALLBACK-WORD>\b",)),
]
EXCLUSIONS = (r"\b<SUBTOTAL-LIKE>\b", r"\b<PAYMENT-LIKE>\b", ...)
BREAKS     = (r"\b<SUMMARY-HEADER>\b",)

candidates = []
dates      = []
for text, _label in ocr_variants(path, cache_dir=CACHE):
    c = extract_by_priority(text, TIERS, EXCLUSIONS, section_break_patterns=BREAKS)
    if c is not None:
        candidates.append(c)
    dates.extend(parse_date_candidates(text, day_first=True))

best_amount = vote_candidates(candidates)
best_date   = pick_best_date(dates)
```

### 3. Known OCR digit confusions on printed amounts

Tesseract on scanned receipts regularly confuses glyphs. When tier matching
fails, check for these before writing custom logic:

| Printed | Common OCR misread                  |
| ------- | ----------------------------------- |
| `0`     | `O`, `o`, `D`, `Q`, `u` (worn ink)  |
| `1`     | `l`, `I`, `|`, `i`                  |
| `5`     | `S`, `s`                            |
| `8`     | `B`                                 |
| `2`     | `Z`                                 |
| `9`     | `g`, `q`                            |
| `.`     | `,` or dropped entirely (e.g. `1000` for `10.00`) |
| `:`     | sometimes used instead of `.` (e.g. `92:80`)      |

`field_extraction.normalize_ocr_digits(token)` applies these substitutions
to a single token when you need an escape hatch.

### 4. Hitting iteration budgets

**Write a valid, complete output file EARLY and iterate on quality afterwards.**
A partially-correct output beats a perfect-but-never-written one. The common
failure mode on receipt-extraction tasks is:

1. Over-inspect the first few images to design the perfect pipeline.
2. Re-run OCR dozens of times while debugging regexes (uncached).
3. Run out of iterations before the output file is ever produced.

Instead:

1. OCR the whole batch once with `DEFAULT_VARIANTS` + caching.
2. Produce the output file immediately with best-effort extraction (null
   when uncertain).
3. Diagnose remaining failures from the cached text without re-OCR'ing.
4. Only widen to `ALL_VARIANTS` for the specific images that are still
   failing.


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
