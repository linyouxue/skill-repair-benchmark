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
3. **Scaling** - Upscale small images (e.g., 2x or 3x) before OCR to improve character recognition
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


## Structured Field Extraction from Receipts

> Scope: this section applies ONLY when the current task supplies a receipt-style
> image **and** declares (in its task prompt) a keyword priority list, an
> exclusion keyword list, and/or a convention for how failed extractions are
> written back. It is a post-OCR text-processing overlay. It does NOT change the
> generic OCR flow above, the JSON output schema, or any guidance for
> non-receipt documents. Do not import these rules into `openai-vision`, `pdf`,
> `video-frame-extraction`, or into `xlsx` guidance for unrelated tasks.
>
> Negative boundary: never fabricate a value, never fold receipt-specific hints
> (currency tokens, locale date orderings, keyword tiers) into any other skill,
> and never hard-code expected outputs from a particular task.

Receipt OCR failures almost always sit in the layer **between** raw Tesseract
output and the final written field, not inside Tesseract itself. The mechanisms
below are reusable anchors that compose on top of (not instead of) the
Multi-Pass OCR Strategy.

### Mechanism anchor: receipt_total_keyword_priority_disambiguation

When the task prompt supplies a priority list of total-keywords (e.g.
`GRAND TOTAL > TOTAL RM / TOTAL: RM > TOTAL AMOUNT > TOTAL / AMOUNT / TOTAL DUE / AMOUNT DUE / BALANCE DUE / NETT TOTAL / NET TOTAL`)
and an exclusion list (e.g. `SUBTOTAL`, `SUB TOTAL`, `TAX`, `GST`, `SST`,
`DISCOUNT`, `CHANGE`, `CASH TENDERED`), use **exactly those tiers and exclusions
as given by the task** – do not reorder, drop, or silently extend them. Then
apply this deterministic selection procedure to the raw OCR text:

1. **Normalize once.** Split OCR output into non-empty lines. For keyword
   matching only, build a canonicalized copy of each line (uppercase, collapse
   whitespace, strip trailing punctuation). Numeric extraction still runs on
   the original line.
2. **Detect a summary-section cutoff.** Scan lines in order; if a line matches
   `GST\s*SUMMARY`, `TAX\s*SUMMARY`, `SST\s*SUMMARY`, or a tax-table column
   header such as `Amount\s*\(RM\)\s*Tax\s*\(RM\)` / `Tax\s*Code`, record its
   index. All lines **after** that index are ineligible as total candidates
   (they are part of a tax breakdown table and reuse words like "Total" or
   "Amount" as column labels).
3. **Walk the tiers in the given priority order.** For each tier:
   a. Collect every eligible (pre-cutoff) line whose canonicalized form
      contains a tier keyword and does **not** contain any exclusion keyword.
   b. Also exclude lines that are tabular column headers – i.e. lines in which
      a tier keyword co-occurs with other column tokens such as
      `DESCRIPTION`, `ITEM`, `QTY`, `U.PRICE`, `UNIT PRICE`, `PRICE` (these
      precede the first line item, not the summary total).
   c. Within the surviving candidates, iterate from last to first and accept
      the first line whose own text yields a parseable monetary token (see
      `monetary_two_decimal_invariant`).
4. **Guarded split-line fallback.** Only when the chosen keyword line contains
   **zero digits** may you consult the *immediately following* non-empty line
   for its last monetary token. The fallback line itself must (a) be
   pre-cutoff, (b) not match any exclusion keyword, and (c) not match a
   payment/tender keyword: `CASH`, `CASH RECEIVED`, `CASH TENDERED`,
   `TENDERED`, `PAYMENT`, `PAID`, `RECEIVED`, `CHANGE`, `VISA`, `MASTERCARD`,
   `MASTER`, `CARD`, `CREDIT`, `DEBIT`. If the keyword line contains digits
   that failed numeric parsing, that is an OCR corruption, not a line split –
   do **not** fall through; back off to an earlier same-tier candidate
   instead.
5. **Tier fall-through only on empty tier.** Only move to the next priority
   tier when the current tier yields no accepted candidate. Never let a lower
   tier override a successful higher-tier match.

### Mechanism anchor: monetary_two_decimal_invariant

Receipt totals are printed with exactly two fractional digits. Treat this as a
structural invariant on the monetary-token regex used for total extraction
(not for prices, quantities, dates, IDs, or any other numeric field):

- Primary pattern: `(?<![\w.])(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})(?![\w.])`.
- A one-decimal match (`88.1`) is treated as an OCR truncation artifact and
  rejected in favor of another candidate in the same tier. Do not silently
  pad a one-decimal value to two decimals.
- Normalize thousands separators (`1,234.56` → `1234.56`) before formatting
  the final written string to `"{:.2f}"`.

### Mechanism anchor: ocr_amount_normalization_and_arithmetic_crosscheck

Tesseract regularly substitutes letters for digits inside the amount token
(`O/o/Q → 0`, `l/I/| → 1`, `S → 5`, `B → 8`, `Z → 2`, `u → 0`, `G → 6`). Apply
confusable substitution **only** inside tokens that are already dominated by
digits and decimal points **and** sit on a line that matched a total/amount
tier keyword; never apply it to free text, product names, invoice IDs, phone
numbers, GST IDs, or dates. After substitution, re-apply the two-decimal
regex. If both subtotal and tax are confidently parsed on the same receipt,
prefer a candidate consistent with `subtotal + tax − discount ± rounding`
over an outlier that differs by exactly one leading-digit substitution; skip
the arithmetic check when subtotal/tax are not both reliably present.

### Mechanism anchor: multi_variant_consensus_over_tier_priority

When the Multi-Pass OCR Strategy produces several candidate `(tier, value,
anchor_type)` tuples for the same receipt, reconcile them before writing:

1. Rank candidates by `(tier_rank, corroborated_support, cross_variant_support,
   position)` in that order.
2. **Corroborated support** = number of *other* total-adjacent lines in the
   same variant whose parsed value matches the candidate within rounding
   tolerance (e.g. a matching `Subtotal`, a matching `Payment`, or
   `Cash − Change`). A single candidate corroborated by another non-tier
   anchor outranks a higher cross-variant frequency with no corroboration.
3. **Cross-variant support** is used only to break ties among equally
   corroborated candidates at the same tier.
4. Never use consensus voting to override a strictly higher-priority tier when
   the higher tier has a cleanly anchored match; never use it to pick numbers
   that did not match any tier keyword.

### Mechanism anchor: conditional_multi_pass_ocr_on_noisy_numeric_fields

The Multi-Pass OCR Strategy section above is additive: you do not need to run
all variants on every image. Trigger an extra OCR pass only when the chosen
total line contains non-`[0-9.,]` characters inside the numeric span, the
monetary regex fails on every tier, or no date candidate passes validation. A
reasonable receipt-tuned fallback set is grayscale + `ImageOps.autocontrast`
at 1x, 2x, and 3x upscales combined with `--psm 6` and `--psm 4`. This is a
fallback, not a default: do not run exhaustive variant sweeps unconditionally
on large batches.

### Mechanism anchor: receipt_date_label_binding_and_locale

Receipts often contain more than one date-like token (transaction date, print
timestamp, closing date, loyalty/promo date). Bind the extracted date to a
label and locale rather than taking the first regex match:

1. Prefer lines whose canonicalized text contains `DATE`, `INVOICE DATE`, or
   OCR variants such as `DATA` / `DAIE` (collapse to `DATE` after
   normalization), and that are **not** preceded by `PRINT`, `CLOSED`,
   `CLOSING`, `FRN`, `LOYALTY`, or `PROMO`.
2. If the task prompt declares a locale (e.g. Malaysian receipts: DD/MM/YYYY
   primary, DD/MM/YY and DD-MM-YY secondary), parse under that convention
   first. In the absence of a declared locale, do not assume one.
3. When a batch of related receipts is processed together, infer the
   dominant day/month ordering from unambiguous rows (any row whose first
   component exceeds 12 fixes the ordering) and apply it to ambiguous rows
   where both components are ≤12. Never override an unambiguous row based on
   batch majority.
4. Emit the chosen date in ISO 8601 (`YYYY-MM-DD`).

### Mechanism anchor: receipt_date_lenient_parse

If the strict date regex fails, run a bounded salvage pass before giving up:

- Allow `I`, `l`, `|` as separator or digit substitutes near a `DATE` label.
- Accept an 8-digit run adjacent to a date label and segment it as `DDMMYYYY`
  (or `YYYYMMDD` when the first four digits form a plausible year), only if
  the resulting `(day, month, year)` triple is calendar-valid.
- For a date-shaped token with exactly one out-of-range component, enumerate
  single-character substitutions from the OCR confusables table and accept a
  repair only if (a) exactly one candidate is calendar-valid and (b) its
  year/month/day fall in a plausible receipt range.
- Do not use lenient parsing to fabricate a date when no date-shaped token
  exists, and do not apply 8-digit segmentation to numeric IDs or phone
  numbers that happen to be eight digits long.

### Mechanism anchor: null_vs_empty_string_contract

When the task contract declares that a failed extraction must be written as
`null`, the writeback must distinguish "no value" from "empty value":

- Return Python `None` from the extraction function on failure, never `""`,
  `"None"`, `"nan"`, or a formatted string.
- Pass `None` directly into `openpyxl` cell / pandas DataFrame cell
  assignments; do not route it through `f"{value}"` or `str(value)`.
- Do not generalize this to tasks whose contract uses `""` or a specific
  placeholder; the rule is scoped to the current receipt-extraction task
  family. See `xlsx/SKILL.md` for the writeback-side companion note.

### Mechanism anchor: xlsx_delivery_contract_self_check (cross-reference)

After writing the final workbook for a receipt-extraction task, reload it
with `openpyxl.load_workbook(path, data_only=True)` and assert the task's
declared schema (sheet name, column order, row ordering, per-cell type)
before terminating. Verify that cells intended as `null` satisfy
`cell.value is None` – not `cell.value == ""`. See `xlsx/SKILL.md`
"Preserving null vs empty string on writeback" for the generic form.

### Workflow note: batch-diagnostic-then-batch-edit

For batch OCR extraction over N images, prefer a single diagnostic pass that
dumps, per image, the per-variant OCR slice around keywords, the candidate
`(tier, value, anchor)` list, and the current prediction. Then plan a small
consolidated set of pattern/variant edits that address several images
together, and re-run once. Avoid an iteration-per-image interactive debug
loop; it exhausts iteration budgets without converging the heuristics.


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
- [ ] For receipt-extraction tasks: the chosen total line matched a declared
      priority tier (not a tabular column header, not a post-summary line);
      the amount passes the two-decimal invariant; failed extractions are
      emitted as Python `None` rather than `""`.


## Limitations

- Tesseract works best with printed text; handwriting recognition is limited
- Accuracy decreases with decorative fonts, artistic text, or extreme stylization
- Mathematical equations and special notation may not extract accurately
- Redacted or watermarked text cannot be recovered
- Severe image degradation (blur, noise, low resolution) reduces accuracy
- Complex multi-column layouts may require custom PSM configuration


## Version History

- **1.0.0** (2026-01-13): Initial release with Tesseract/pytesseract OCR
- **1.1.0**: Added "Structured Field Extraction from Receipts" overlay with
  bounded mechanism anchors for keyword-priority total selection, two-decimal
  monetary invariant, OCR amount normalization, multi-variant consensus,
  label-bound date extraction, lenient date salvage, and the
  null-vs-empty-string writeback contract. Overlay is scoped to receipt-style
  OCR tasks that declare their own keyword/exclusion/null conventions and
  does not alter generic OCR behavior.
