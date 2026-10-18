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

## Output Requirements (structured vs raw OCR)

This skill supports two common outputs:

1) **Raw OCR text** (exploration/debugging)
2) **Structured extraction** (benchmark-style outputs such as receipts)

### Receipt benchmark output requirement (date + total_amount)
When the task requires receipt statistics, the output is typically a table with:
- `filename`
- `date` (ISO `YYYY-MM-DD`, or null on failure)
- `total_amount` (string with exactly 2 decimals, or null on failure)

**Important:** In XLSX, null must be written as a blank cell (use Python `None`), not the literal strings `"null"` or `""`.

Raw OCR JSON can still be useful internally (for debugging), but do not force JSON output when the task specifies Excel/CSV.


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


## Receipt OCR pipeline for (date, total_amount)

This section is optimized for receipt statistics extraction where the target fields are **date** and **total amount**.

### Recommended Tesseract configs (receipts + numeric fields)
Use `--oem 1` (LSTM) and try **1–2 PSMs** only.

```python
# General receipt text (keeps spacing for line parsing)
RECEIPT_TEXT_CFGS = [
    "--oem 1 --psm 6 -c preserve_interword_spaces=1",
    "--oem 1 --psm 4 -c preserve_interword_spaces=1",
]

# Numeric-focused pass for totals (reduce noise)
RECEIPT_NUM_CFGS = [
    "--oem 1 --psm 6 -c preserve_interword_spaces=1 -c tessedit_char_whitelist=0123456789.,:-/RM$ ",
]
```

### Bounded multi-pass strategy (with confidence selection)
1) Run OCR on the full receipt with `RECEIPT_TEXT_CFGS`.
2) If total/date missing or low confidence, run a second OCR on **bottom ROI** with numeric-focused config.
3) Select the best pass by mean word confidence (filtering invalid conf = -1).

```python
import pytesseract
from pytesseract import Output

def ocr_with_mean_conf(img, config: str, lang: str = "eng") -> tuple[str, float]:
    data = pytesseract.image_to_data(img, lang=lang, config=config, output_type=Output.DICT)
    confs = []
    for c in data.get("conf", []):
        try:
            c = float(c)
        except Exception:
            continue
        if c >= 0:
            confs.append(c)
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    txt = pytesseract.image_to_string(img, lang=lang, config=config)
    return txt, mean_conf

def best_ocr_text(img, cfgs) -> str:
    best = ("", -1.0)
    for cfg in cfgs:
        txt, mc = ocr_with_mean_conf(img, cfg)
        if mc > best[1] and txt.strip():
            best = (txt, mc)
    return best[0]
```

### Deterministic field extraction with validation
Parse **line-by-line** from OCR output. Use keyword tiers + exclusions for totals and multi-format parsing for dates.

#### Total extraction (keyword tiers + exclusion + same/next-line fallback)
Rules:
- Search tiers in order: `GRAND TOTAL` → `TOTAL RM`/`TOTAL: RM` → `TOTAL AMOUNT` → general totals (`TOTAL`, `AMOUNT`, `TOTAL DUE`, ...)
- Skip lines containing exclusions (`SUBTOTAL`, `TAX`, `GST`, `SST`, `DISCOUNT`, `CHANGE`, `CASH TENDERED`)
- Prefer totals **near bottom**: if multiple candidates, prefer the last match or largest plausible value (avoid tiny unit prices).
- Money regex supports comma separators.

```python
import re

TOTAL_KEYWORDS_PRIORITY = [
    ["GRAND TOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    ["TOTAL DUE", "AMOUNT DUE", "BALANCE DUE", "NETT TOTAL", "NET TOTAL", "TOTAL", "AMOUNT"],
]
EXCLUDE_KEYWORDS = ["SUBTOTAL", "SUB TOTAL", "TAX", "GST", "SST", "DISCOUNT", "CHANGE", "CASH TENDERED"]
MONEY_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{2})(?!\d)")

def _money_last(s: str) -> str | None:
    ms = MONEY_RE.findall(s)
    if not ms:
        return None
    v = ms[-1].replace(",", "")
    try:
        return f"{float(v):.2f}"
    except Exception:
        return None

def extract_total_amount(ocr_text: str) -> str | None:
    lines = [ln.strip() for ln in ocr_text.splitlines() if ln.strip()]
    u = [ln.upper() for ln in lines]

    def excluded(uline: str) -> bool:
        return any(k in uline for k in EXCLUDE_KEYWORDS)

    candidates: list[tuple[int, str]] = []  # (line_index, amount)

    for tier in TOTAL_KEYWORDS_PRIORITY:
        for i, uline in enumerate(u):
            if excluded(uline):
                continue
            if any(k in uline for k in tier):
                amt = _money_last(lines[i])
                if amt is None and i + 1 < len(lines):
                    amt = _money_last(lines[i + 1])
                if amt is not None:
                    candidates.append((i, amt))
        if candidates:
            break

    if not candidates:
        return None

    # Prefer candidate near bottom; break ties by larger numeric value
    def key(t):
        i, amt = t
        return (i, float(amt))

    return max(candidates, key=key)[1]
```

#### Date extraction (multi-format + normalization + plausibility)
Support:
- `YYYY-MM-DD`, `YYYY/MM/DD`
- `DD-MM-YYYY`, `DD/MM/YYYY`
- `DD MON YYYY` (month names)

Validation:
- Year range plausibility (e.g., 1990–2035)

```python
from datetime import datetime

DATE_PATS = [
    re.compile(r"(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})"),
    re.compile(r"(\d{1,2})[\-/](\d{1,2})[\-/](\d{4})"),
]
MONTHS = {"JAN":1,"JANUARY":1,"FEB":2,"FEBRUARY":2,"MAR":3,"MARCH":3,"APR":4,"APRIL":4,"MAY":5,
          "JUN":6,"JUNE":6,"JUL":7,"JULY":7,"AUG":8,"AUGUST":8,"SEP":9,"SEPT":9,"SEPTEMBER":9,
          "OCT":10,"OCTOBER":10,"NOV":11,"NOVEMBER":11,"DEC":12,"DECEMBER":12}
MONTH_NAME_PAT = re.compile(r"\b(\d{1,2})\s*([A-Z]{3,9})\s*(\d{2,4})\b")

def _valid_year(y: int) -> bool:
    return 1990 <= y <= 2035

def extract_date_iso(ocr_text: str) -> str | None:
    lines = [ln.strip() for ln in ocr_text.splitlines() if ln.strip()]
    # Prefer lines with DATE/INVOICE/RECEIPT hints
    scored = []
    for i, ln in enumerate(lines):
        up = ln.upper()
        score = 2 if any(k in up for k in ["DATE", "INVOICE", "RECEIPT"]) else 1
        scored.append((score, -i, ln))  # earlier lines slightly preferred within same score
    scored.sort(reverse=True)

    for _, __, ln in scored:
        for pat in DATE_PATS:
            m = pat.search(ln)
            if not m:
                continue
            a, b, c = map(int, m.groups())
            try:
                if len(str(a)) == 4:
                    y, mo, d = a, b, c
                else:
                    d, mo, y = a, b, c
                if not _valid_year(y):
                    continue
                return datetime(y, mo, d).strftime("%Y-%m-%d")
            except Exception:
                pass

        up = ln.upper()
        m = MONTH_NAME_PAT.search(up)
        if m:
            d, mon, y = m.groups()
            y = int(y)
            if y < 100:
                y += 2000 if y < 70 else 1900
            if mon in MONTHS and _valid_year(y):
                try:
                    return datetime(y, MONTHS[mon], int(d)).strftime("%Y-%m-%d")
                except Exception:
                    pass

    return None
```

### Batch reliability requirements (timeouts, checkpoints, and guaranteed output)
Receipt OCR in bulk can stall. To ensure the final artifact exists and partial failures don’t abort the whole run:
- Use **per-image timeouts** (e.g., via `signal.alarm` on Linux) and catch exceptions.
- Log progress every image (filename + extracted fields + warnings).
- Save checkpoints every N files.
- Always create `/app/workspace/stat_ocr.xlsx` even if some images fail (write `None` for missing fields).
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



### Receipt-oriented preprocessing recipe (recommended for date/total extraction)
Receipts often have faint thermal text, skew, and background texture. Use a lightweight but receipt-friendly pipeline:

**Recipe (PIL-only, fast):**
1) grayscale → 2) autocontrast → 3) optional upscale (1.5–2x) → 4) binarize (threshold) → 5) median denoise → 6) optional crop ROI (bottom for totals)

```python
from PIL import Image, ImageOps, ImageFilter

def preprocess_receipt(img: Image.Image, upscale_if_small: bool = True, threshold: int | None = 160) -> Image.Image:
    # 1) grayscale
    img = ImageOps.grayscale(img)
    # 2) contrast stretch
    img = ImageOps.autocontrast(img)
    # 3) upscale small receipts (helps digits)
    if upscale_if_small and min(img.size) < 1000:
        img = img.resize((img.size[0] * 2, img.size[1] * 2))
    # 4) threshold to reduce background (optional)
    if threshold is not None:
        img = img.point(lambda p: 255 if p >= threshold else 0)
    # 5) denoise (median is good for salt/pepper)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    return img

def bottom_roi(img: Image.Image, frac: float = 0.38) -> Image.Image:
    """Crop bottom region where totals frequently appear."""
    w, h = img.size
    y0 = int(h * (1 - frac))
    return img.crop((0, y0, w, h))
```

**Deskew note (bounded):** If receipts are rotated/skewed, first try Tesseract OSD (`--psm 0`) to detect rotation, or run one extra pass with `--psm 11` (sparse text). Keep retries capped (1–2) for batch throughput.
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


## Practical checklist for receipt-stat tasks (jpg-ocr-stat)

- Preprocess with grayscale+autocontrast; add threshold+denoise for thermal paper.
- Run at most 2 OCR passes per image: full image text + optional bottom ROI numeric pass.
- Use `--oem 1` and `--psm 6` or `--psm 4`; keep `preserve_interword_spaces=1` for line parsing.
- Parse totals with keyword tiers + exclusions; allow same-line and next-line amount.
- Parse dates in multiple formats; normalize to ISO; validate year plausibility.
- Batch safety: per-image timeout + exception isolation; checkpoint; always save final XLSX to the exact path; verify sheetname/columns after saving.
