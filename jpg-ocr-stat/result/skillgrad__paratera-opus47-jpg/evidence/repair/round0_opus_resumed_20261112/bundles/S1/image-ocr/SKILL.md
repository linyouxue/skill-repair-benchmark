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
3. **Scaling** - Upscale small images (e.g., 2x or 3x LANCZOS) before OCR to improve character recognition
4. **Thresholding** - Convert to binary using `img.point(lambda p: 255 if p > threshold else 0)` with different threshold values (e.g., 100, 128)
5. **Sharpening** - Apply `ImageFilter.SHARPEN` to improve edge clarity


## Multi-Pass OCR Strategy

Default `pytesseract.image_to_string(img)` is a single pass at PSM 3 with no
preprocessing. For any task that parses OCR text into structured fields
(receipts, invoices, forms, tabular scans) under an exact-string verifier,
a single pass is unsafe: one misread glyph (digit confusions, decimals
lost to space/colon, word spacing dropped so two tokens concatenate) will
silently propagate into the final answer and no downstream rule can
recover it.

Run multiple preprocessing/PSM variants, keep **per-variant line-level
text** (do not merge into one blob), and let the structured extractor vote
across variants on each field independently.

```python
from PIL import Image, ImageOps
import pytesseract

def ocr_variants(image_path):
    """Return list of (variant_name, text) pairs — one entry per pass."""
    img = Image.open(image_path)
    gray = ImageOps.autocontrast(img.convert("L"))
    w, h = gray.size
    upscaled = ImageOps.autocontrast(
        gray.resize((w * 3, h * 3), Image.LANCZOS))
    passes = [
        ("default_psm3", img, "--psm 3"),
        ("gray_autocontrast_psm6", gray, "--psm 6"),
        ("upscale_3x_psm4", upscaled, "--psm 4"),
    ]
    out = []
    for name, variant, cfg in passes:
        try:
            out.append((name, pytesseract.image_to_string(variant, config=cfg)))
        except Exception:
            out.append((name, ""))
    return out
```

Decision rule: if the downstream task consumes OCR text verbatim (free-text
summarisation, keyword search), one pass is fine. If the downstream task
picks fields with keywords/regex and the answer must match an exact
string, use `ocr_variants` and vote per field — never ship a pipeline that
calls `image_to_string(img)` once on the raw PIL image.


## Candidate Selection from Multi-Variant Text

When the downstream task selects a specific field (an amount, a date, a
record identifier) from the multi-variant OCR text, use these rules. They
apply across receipts, invoices, forms, and any scanned-document family
where keyword lines are sometimes mangled and value tokens sometimes have
single-glyph corruption.

Rule 1 — **Collect candidates from every variant separately.** Do not
concatenate variant texts. Extract keyword-matched candidates from each
variant's line-level text, keeping tier/specificity/line-index metadata.

Rule 2 — **Within-text frequency beats cross-variant majority.** When
ranking candidates, prefer values whose exact string also appears on other
corroborating lines in the SAME variant (e.g., the same amount on
Subtotal, Payment, and Rounded Total lines). Cross-variant majority is a
tiebreaker only — two low-quality variants can agree on the same wrong
digit and outvote a single correct variant.

Rule 3 — **Scope regex tolerance to keyword-matched lines, not globally.**
If a keyword line matches but the value regex fails because of OCR noise
(decimal dropped to space/colon, letter-shaped digit, trailing punctuation),
normalize those glyphs only on that one line before re-running the value
regex. Keeping the normalization local preserves other lines (time stamps,
IDs) that should not be rewritten.

Rule 4 — **Anchor label-driven fields (dates, IDs) to the literal label
token on the same OCR line.** Free-standing look-alike tokens elsewhere
(receipt IDs with embedded digits, handwritten annotations, time
components of `HH:MM:SS`) must be rejected. For regional locales where
the sample proves a format (DD/MM/YYYY vs MM/DD/YYYY), default to that
format; fall back to the alternative only when the default is
arithmetically implausible.

```python
from collections import Counter
import re

def rank_variant_field(per_variant_candidates):
    """per_variant_candidates: [(variant_name, text, [(tier, spec, value, line_idx), ...])].
    Returns (value, variant_name) or None."""
    picks = []
    for name, text, cands in per_variant_candidates:
        if not cands:
            continue
        # Within-variant: tier, then specificity, then within-text frequency.
        best_tier = min(c[0] for c in cands)
        same_tier = [c for c in cands if c[0] == best_tier]
        best_spec = min(c[1] for c in same_tier)
        pool = [c for c in same_tier if c[1] == best_spec]
        def score(c):
            freq = len(re.findall(re.escape(c[2]), text))
            return (freq, c[3])  # prefer corroborated value, then later line
        winner = max(pool, key=score)
        picks.append((winner[0], winner[1], winner[2], text, name))
    if not picks:
        return None
    # Cross-variant tiebreak: combined within-text frequency.
    best_tier = min(p[0] for p in picks)
    same_tier = [p for p in picks if p[0] == best_tier]
    best_spec = min(p[1] for p in same_tier)
    pool = [p for p in same_tier if p[1] == best_spec]
    chosen = max(pool,
        key=lambda p: len(re.findall(re.escape(p[2]), p[3])))
    return chosen[2], chosen[4]
```

Verification: after ranking, confirm the chosen value appears at least
once as a substring in the chosen variant's text. If it does not, the
ranker produced an artefact — log the full candidate list and drop to the
next-priority non-empty variant's winner. If every variant produced zero
candidates for an item, emit a warning explaining why (not a silent null);
corrective action is to add one more OCR variant (e.g. additional PSM,
further upscale) and re-rank before accepting null.


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


## Common Pitfalls

- **Single-pass default OCR on structured extraction tasks.** `image_to_string(img)` on the raw image produces one glyph mis-read per handful of documents; those mis-reads propagate into exact-string deliverables. Use `ocr_variants` for anything that will be parsed into named fields.
- **Cross-variant majority voting without within-text corroboration.** Two low-quality variants can agree on the same wrong value and outvote a correct single variant; within-text frequency (same value across corroborating lines of one variant) is the stronger signal.
- **Globally loosening regexes to absorb OCR noise.** Loosening value/keyword regexes across the whole text catches new false positives on time stamps and IDs. Scope normalization (`:`→`.`, space→`.`, `O`→`0`, dropped trailing letters) to lines already matched by a priority keyword.
- **Picking look-alike tokens for label-anchored fields.** Date-shaped tokens appear in receipt IDs and inside time stamps; always anchor to the literal label on the same OCR line, and reject tokens whose character window contains a `HH:MM` pattern.
- **Writing partial results and never re-running end-to-end.** When heuristics are iterated per-image and the deliverable is written after each edit, the shipped artifact can predate the best-known algorithm when budget runs out. Cache multi-variant OCR once, iterate in-memory, and overwrite the deliverable only after a full-corpus pass — see xlsx/SKILL.md "Batch image-to-xlsx pipelines".


## Limitations

- Tesseract works best with printed text; handwriting recognition is limited
- Accuracy decreases with decorative fonts, artistic text, or extreme stylization
- Mathematical equations and special notation may not extract accurately
- Redacted or watermarked text cannot be recovered
- Severe image degradation (blur, noise, low resolution) reduces accuracy
- Complex multi-column layouts may require custom PSM configuration


## Version History

- **1.0.0** (2026-01-13): Initial release with Tesseract/pytesseract OCR
