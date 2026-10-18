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



## Receipt-Specific Field Extraction (Date + Total)

When the goal is **structured fields** (e.g., `date`, `total_amount`) rather than full text, apply deterministic heuristics to OCR text.

### Total amount heuristic (keyword priority + exclusions + next-line fallback)
- Scan lines in order and search by keyword tiers (most specific → least specific).
- **Skip** lines containing exclusion keywords to avoid subtotals/taxes.
- Extract the **last monetary-looking number** on the matched line; if none, look at the **next line** and use the last number there.
- Support comma separators like `1,234.56`.

### Date heuristic
- Look for common receipt date patterns and normalize to ISO `YYYY-MM-DD`.
- If multiple dates exist, prefer ones near keywords like `DATE`, `INVOICE`, `RECEIPT` (if present), otherwise take the first plausible date.

```python
import re
from datetime import datetime

TOTAL_KEYWORDS_PRIORITY = [
    ["GRAND TOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    ["TOTAL DUE", "AMOUNT DUE", "BALANCE DUE", "NETT TOTAL", "NET TOTAL", "TOTAL", "AMOUNT"],
]
EXCLUDE_KEYWORDS = [
    "SUBTOTAL", "SUB TOTAL", "TAX", "GST", "SST", "DISCOUNT", "CHANGE", "CASH TENDERED",
]

_money_re = re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{2})")

def _last_money(s: str):
    m = _money_re.findall(s)
    if not m:
        return None
    val = m[-1].replace(",", "")
    # Ensure 2 decimals already; keep as string
    return f"{float(val):.2f}"

def extract_total_amount(ocr_text: str):
    lines = [ln.strip() for ln in ocr_text.splitlines() if ln.strip()]
    ulines = [ln.upper() for ln in lines]

    def excluded(u: str) -> bool:
        return any(k in u for k in EXCLUDE_KEYWORDS)

    for tier in TOTAL_KEYWORDS_PRIORITY:
        for i, uln in enumerate(ulines):
            if excluded(uln):
                continue
            if any(k in uln for k in tier):
                amt = _last_money(lines[i])
                if amt is not None:
                    return amt
                if i + 1 < len(lines):
                    amt2 = _last_money(lines[i + 1])
                    if amt2 is not None:
                        return amt2
    return None

_date_patterns = [
    # YYYY-MM-DD, YYYY/MM/DD
    re.compile(r"(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})"),
    # DD-MM-YYYY, DD/MM/YYYY
    re.compile(r"(\d{1,2})[\-/](\d{1,2})[\-/](\d{4})"),
]

def extract_date_iso(ocr_text: str):
    lines = [ln.strip() for ln in ocr_text.splitlines() if ln.strip()]
    # Prefer lines containing DATE-like hints if available
    scored = []
    for idx, ln in enumerate(lines):
        u = ln.upper()
        score = 1
        if any(k in u for k in ["DATE", "INVOICE", "RECEIPT"]):
            score = 2
        scored.append((score, idx, ln))
    scored.sort(reverse=True)

    for _, _, ln in scored:
        for pat in _date_patterns:
            m = pat.search(ln)
            if not m:
                continue
            parts = list(map(int, m.groups()))
            try:
                if len(str(parts[0])) == 4:
                    y, mo, d = parts
                else:
                    d, mo, y = parts
                dt = datetime(y, mo, d)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
    return None
```

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



### Timeout-safe batch execution + progress checkpoints (mandatory for large directories)
When processing many images, implement **incremental saves** so that partial progress is persisted even if the run is interrupted.

Recommended patterns:
- Write an intermediate JSON/CSV checkpoint every N images.
- For Excel output, **save repeatedly** (or write a temporary file then atomically replace) so `/app/workspace/stat_ocr.xlsx` exists throughout.
- Log progress with counts and last filename.
- Before declaring completion, enforce postconditions:
  - `os.path.exists(output_path)` is `True`
  - Row count equals the number of processed images

```python
import os
from pathlib import Path

def safe_write_excel(workbook, final_path: str):
    tmp = final_path + ".tmp"
    workbook.save(tmp)
    os.replace(tmp, final_path)

# Postcondition checks (use at end of run)
# assert os.path.exists(OUT_PATH)
# assert ws.max_row == len(records) + 1  # + header
```
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


## Receipt Batch OCR Strategy (Directory Workloads)

For directories containing many receipt images, prioritize **throughput and reliability** over exhaustive multi-pass variants.

### Recommendation: single-pass OCR with tuned config
- Use **one preprocessing pipeline** (grayscale → autocontrast → optional resize/threshold) and **one OCR pass** per image.
- Prefer `--psm 6` (uniform block) for most receipts; optionally fall back to `--psm 4` if output is empty.
- Restrict the character set for receipt totals/dates to reduce noise.

```python
import pytesseract
from PIL import Image, ImageOps

RECEIPT_CFG = "--oem 1 --psm 6 -c preserve_interword_spaces=1"
# Optional: for numeric-heavy fields (totals), you may also try:
# NUMERIC_CFG = RECEIPT_CFG + " -c tessedit_char_whitelist=0123456789.,:RM$-/"

def preprocess_receipt(img: Image.Image) -> Image.Image:
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    # Lightweight resize: upscale small images once (avoid repeated variants)
    if min(img.size) < 900:
        scale = 2
        img = img.resize((img.size[0]*scale, img.size[1]*scale))
    return img

def ocr_receipt_text(image_path: str, lang: str = "eng") -> str:
    img = preprocess_receipt(Image.open(image_path))
    txt = pytesseract.image_to_string(img, lang=lang, config=RECEIPT_CFG)
    if not txt.strip():
        # minimal fallback only if needed
        txt = pytesseract.image_to_string(img, lang=lang, config="--oem 1 --psm 4")
    return txt
```

### Avoid excessive repeated OCR variants
Multi-pass OCR (many PSMs × many preprocessing variants) can cause long runtimes and stalls in batch tasks. Use it only for a small subset of failures (e.g., empty output), and cap fallbacks to 1–2 attempts.


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


- [ ] For batch tasks, progress is checkpointed (intermediate save every N files)
- [ ] Required output artifact exists at the exact required path (`os.path.exists()`)
- [ ] Output row count matches number of input images (excluding header)
- [ ] If producing Excel: exactly one sheet with the required name; no extra sheets/rows/columns
