---
name: image-ocr
description: Extract image text with Tesseract and resolve receipt date glyph ambiguities, rounded payable totals, and evidence-preserving field updates.
---

# Image OCR Skill

## Purpose
This skill enables accurate text extraction from image files (JPG, PNG, etc.) using Tesseract OCR via the `pytesseract` Python library. It is suitable for scanned documents, screenshots, photos of text, receipts, forms, and other visual content containing text.

For structured receipt fields, follow **Structured Field Decision Branches** below
after the initial extraction. Encode the applicable branches in the extraction
and update logic before accepting field values; the raw OCR examples are not a
complete field-selection algorithm.

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
The raw OCR helper returns JSON conforming to this schema. For a caller-requested
spreadsheet, preserve the caller's final schema and keep auxiliary evidence in a
separate working file:

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
3. **Scaling** - Upscale small images (e.g., 2x or 3x) before OCR to improve character recognition. For faint or thin fonts on receipts, 3x with autocontrast frequently recovers decimal points and punctuation that 1x/2x lose.
4. **Thresholding** - Convert to binary using `img.point(lambda p: 255 if p > threshold else 0)` with different threshold values (e.g., 100, 128)
5. **Sharpening** - Apply `ImageFilter.SHARPEN` to improve edge clarity


## Multi-Pass OCR Strategy

For challenging images, a single OCR pass may miss text. Use multiple passes with different configurations:

1. **Try multiple PSM modes** - Different page segmentation modes work better for different layouts (e.g., `--psm 6` for blocks, `--psm 4` for columns, `--psm 11` for sparse text)

2. **Try multiple preprocessing variants** - Run OCR on several preprocessed versions of the same image

3. **Retain results** - Keep each pass's text and source separately for structured-field decisions. Concatenation can improve raw-text coverage, but it loses the evidence needed to select one field value.

```python
def multi_pass_ocr(image_path):
    """Run OCR with multiple strategies and combine results."""
    img = Image.open(image_path)
    gray = ImageOps.grayscale(img)
    w, h = img.size

    # Generate preprocessing variants (include an upscaled variant; 3x often
    # recovers thin punctuation such as the decimal point in prices)
    variants = [
        ImageOps.autocontrast(gray),
        ImageOps.invert(ImageOps.autocontrast(gray)),
        gray.filter(ImageFilter.SHARPEN),
        ImageOps.autocontrast(img.resize((w * 3, h * 3), Image.LANCZOS).convert('L')),
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

### Structured Field Decision Branches

After one batch extraction, save provisional results and a separate evidence
record containing each candidate's raw text, field label, image region, and OCR
source. Evaluate the following triggers for every field, including non-empty and
format-valid fields. Select a branch before selecting a value. A clear field can
be confirmed directly; OCR frequency, keyword rank, and variant order alone are
not confirmation evidence.

#### Branch A — Date glyph inspection before confirmation

**Trigger:** a compact printed numeric date next to `Date` has a month digit read
as `3` or `8`, or any date component has broken strokes, unclear loop closure,
contact with a separator, or conflicting readings. A nearby `Time` line can help
locate the block and provide same-font comparison digits. Apply this branch even
when every OCR variant agrees and the proposed date is calendar-valid. A changed
date candidate after reordering or enlarging OCR variants also triggers review.

**Execute in this order:**
1. Preserve the current raw date and each alternative. Crop the complete `Date`
   line, including its label, separators, day, month, year, and margins; retain the
   neighboring `Time` line when present. Save the original-pixel crop and a larger
   nearest-neighbor copy. Use these as the reference; sharpened, thresholded, or
   smoothed versions can manufacture or erase a connecting stroke.
2. Actually open the saved crop with the image-view tool, such as
   `file_editor(command="view", path="<saved crop path>")`. Saving a PNG or
   printing its OCR text does not complete this step. Examine the uncertain glyph:

   | Visible feature in the original crop | Interpretation to check |
   | --- | --- |
   | Two rightward-curving lobes joined on the right, with open gaps on the left | An open-arc digit such as `3`; do not treat the lobes as two closed rings |
   | A real left-hand connecting stroke closes both the upper and lower holes | A closed-loop digit such as `8`; verify both closures in the original pixels |
   | Apparent closure exists only after thresholding, scaling, or isolated noise bridges a gap | Processing artifact; return to the original crop and keep alternatives pending |

   Compare the glyph with unambiguous printed digits in the same font, including
   the neighboring time when useful. The time supplies glyph shapes, not a month
   value. Inspect the entire month token rather than choosing a digit from its
   overall dark outline. Neither a global `8 -> 3` replacement nor the reverse
   is a valid repair.
3. Use focused line OCR only to generate additional candidate readings. Resolve
   the actual printed glyph using the crop and its label context, then establish
   day/month/year order and convert to ISO. Write a separate date-evidence record
   with the accepted value, crop path, visible distinguishing strokes, and status
   `confirmed`. If the original pixels cannot distinguish the candidates, retain
   status `pending`; format validity, first-variant order, and votes cannot promote
   it to `confirmed`.
4. Load that evidence record on every later extraction. A `confirmed` date is the
   accepted date for the deliverable, independent of new OCR order or votes. Put
   any disagreeing new reading into review without overwriting it. Replace the
   accepted date only after another actual crop inspection supplies stronger
   same-field evidence, and record the reason. A provisional date is not protected
   merely because it happened to appear in an earlier workbook.

**Confirm when:** the image-view operation has occurred, the distinguishing
stroke evidence and complete date context are recorded, and workbook readback
matches the accepted date. When no image-view tool is available, acknowledge that
limitation and keep unresolved glyph ambiguity pending rather than claiming a
visual check. Keep the evidence record outside the requested workbook schema.

#### Branch B — Inclusive total, rounding, and a later final total

**Trigger:** the payment block contains a pre-round total (possibly labeled as
tax-inclusive), a signed rounding adjustment, and a later `TOTAL`, `NET TOTAL`,
`NETT TOTAL`, or other final-payable line. Different amounts in these roles are
not conflicting OCR readings of one field.

**Execute:**
1. Crop and read the whole payment block together. Assign candidates to separate
   roles: subtotal, tax/service components, pre-round payable, signed adjustment,
   final payable, tendered cash, and change. Keep a tax-summary table outside this
   payment block; its own `TOTAL` is not the amount due.
2. Preserve the `+` or `-` on the adjustment. Parse these monetary tokens with
   `Decimal` and check `final_payable == pre_round_payable + signed_adjustment`.
   The sign is part of the value, not punctuation to discard. If the pre-round
   payable already includes tax/service charges, use those components only to
   cross-check it, not to add them again.
3. Select the explicitly printed final-payable amount when the field association
   and arithmetic agree, even if an earlier tax-inclusive amount occurs in more
   OCR passes or has a higher-ranked keyword. The final label can be larger or
   bolder than surrounding text; inspect that line separately if OCR misses it.
4. If a digit or separator is missing or the arithmetic disagrees, review the
   corresponding local crop. Accept the result only after resolving the reading;
   do not invent a rounding adjustment or silently force the arithmetic to fit.

**Confirm when:** the final amount is anchored to its own label and verified
against the printed settlement relation. If no rounding/final-total pattern is
present, resolve the final-payable role from the receipt's actual labels; do not
apply this branch's adjustment speculatively. Keywords such as `GST` identify a
possible component, not an automatic reason to discard an inclusive payable.

#### Branch C — Amount split across lines or repaired digits

**Trigger:** an amount keyword has no number on its line, or a candidate relies
on inserting a decimal, removing an OCR character, or joining separated digits.

**Execute:** crop the label and neighboring lines together. Locate the numeric
region that is visually associated with that label; exclude quantity, date,
identifier, tax-rate, and change fields. Use next-line/trailing tokens only as
candidates. Support each punctuation/digit repair from the original monetary
region, and then apply Branch B if settlement roles are present.

**Confirm when:** both the label association and repaired number are supported.
Neither the last number on a line nor successful parsing clears this branch.

#### Branch D — Reusing confirmed fields after a parser change

**Trigger:** changing shared parsing/selection logic, adding a raw-OCR preference,
or retrying extraction after any fields have been confirmed.

**Execute:** save and reload the confirmed field values with their evidence before
the change. Run the new logic into provisional candidates. Merge only reviewed
updates to unresolved or demonstrably affected fields; retain every other
confirmed field. A changed candidate requires stronger same-field evidence and
a recorded reason before replacing a confirmed value. Rebuild the deliverable
from this merged accepted state, not from fresh unreviewed batch output.

**Confirm when:** a before/after field comparison shows that every replacement
has been reviewed. Execute the write, reopen the destination workbook, and compare
its stored values with the accepted state. Logs or values left only in memory do
not demonstrate delivery. Reserve budget for this final readback instead of
unnecessarily repeating full-batch OCR at the end.

### Numeric Normalization for Receipts and Forms

OCR frequently corrupts decimal separators and digit spacing in monetary amounts.
Apply the following repairs only inside a monetary region associated with its
label, and only when its printed evidence supports the repair (Branch C):

- Replace `:` between digits with `.` (e.g., `92:80` -> `92.80`).
- Collapse a single space between a 1-4 digit group and a 2-digit group into `.` (e.g., `92 80` -> `92.80`, `1 234 56` -> keep the comma-thousands intact but treat trailing ` 56` as decimals only when no other decimal separator is present).
- Reinterpret bare digit clusters of length >=3 whose last two digits look like cents as `X.YY` when no decimal separator was recognized (e.g., `9280` -> `92.80`) **only** when the line contains a strong keyword such as `GRAND TOTAL` and no better candidate exists.
- Remove clearly extraneous surrounding OCR marks; retain decimal/thousands punctuation and any genuine sign, especially on rounding adjustments.
- Accept commas as thousands separators: `1,234.56` -> `1234.56`.

Prefer a well-formed monetary token in the identified field. Next-line candidates
and decimal repairs must pass Branch C; this helper parses a token but does not
decide whether it is the final amount. Keep date and ID parsing separate.

```python
import re
from decimal import Decimal

MONEY_STRICT = re.compile(r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}')

def parse_money(token: str, *, decimal_repair_supported=False):
    """Parse a field-associated monetary token, preserving a printed sign."""
    if token is None:
        return None
    s = token.strip().replace('\u2212', '-')
    if MONEY_STRICT.fullmatch(s):
        return Decimal(s.replace(',', ''))
    if not decimal_repair_supported:
        return None
    # Enable only after the original region establishes the decimal position.
    candidates = [
        re.sub(r'(\d):(\d{2})$', r'\1.\2', s),
        re.sub(r'(\d)\s+(\d{2})$', r'\1.\2', s),
    ]
    if re.fullmatch(r'[+-]?\d{3,}', s):
        candidates.append(s[:-2] + '.' + s[-2:])
    for candidate in candidates:
        if MONEY_STRICT.fullmatch(candidate):
            return Decimal(candidate.replace(',', ''))
    return None
```


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

**Issue**: Keyword detected but no numeric value parsed

- Do not immediately return null. First:
  1. Run Branch C on the label and its neighboring numeric region.
  2. If multiple settlement amounts or rounding appear, run Branch B.
  3. Retain unresolved candidates and continue focused review within the available budget.
- If the field remains unresolved, report extraction failure instead of accepting
  an unrelated but parseable number. Non-empty ambiguous fields use the same
  decision branches; review is not limited to null values.


## Quality Self-Check

Before returning results, verify:

- [ ] Output is valid JSON (use `json.loads()` to validate)
- [ ] All required fields are present (`success`, `filename`, `extracted_text`, `confidence`, `metadata`)
- [ ] Text preserves logical reading order
- [ ] Confidence level reflects actual OCR quality
- [ ] Warnings array includes all detected issues
- [ ] Special characters are properly escaped in JSON

### Structured-Value Extraction Self-Check

When the caller extracts specific fields (amounts, dates, IDs), also verify:

- [ ] For every image where a target keyword (e.g., `GRAND TOTAL`, `TOTAL RM`) is detected in **any** OCR variant, a candidate value was produced, or the reason for failure is explicitly logged.
- [ ] Uncertain printed date components passed Branch A, including legal dates with weak source readings and correlated OCR agreement.
- [ ] Settlement totals passed Branch B where applicable; pre-round, rounded, tax-summary, tendered, and change amounts were kept in separate roles.
- [ ] Decimal repairs and split-line candidates passed Branch C, preserving a genuine adjustment sign.
- [ ] Parser changes and retries passed Branch D; confirmed fields were preserved unless an evidenced correction was accepted.
- [ ] The executed script produced the requested file, and readback matched the accepted fields and caller's schema, coverage, and ordering.


## Limitations

- Tesseract works best with printed text; handwriting recognition is limited
- Accuracy decreases with decorative fonts, artistic text, or extreme stylization
- Mathematical equations and special notation may not extract accurately
- Redacted or watermarked text cannot be recovered
- Severe image degradation (blur, noise, low resolution) reduces accuracy
- Complex multi-column layouts may require custom PSM configuration
- Thin punctuation (decimal points, colons) is often lost or substituted; always attempt numeric normalization before rejecting a value


## Version History

- **1.0.0** (2026-01-13): Initial release with Tesseract/pytesseract OCR
- **1.1.0**: Added value-level voting across variants, numeric normalization guidance for OCR-corrupted amounts, and structured-value extraction self-check.
