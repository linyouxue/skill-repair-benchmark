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

## Structured Receipt Workflow Template

For tasks requiring exact receipt fields, implement the following workflow in
addition to the OCR techniques above. Keep separate OCR observations and
field decisions; merged multi-pass text is an observation, not a field verdict.
Use the task's prescribed output schema for delivery and separate JSON records
for working evidence.

Execute these stages in order: initialize the persistent ledger, checkpoint
the first pass, persist the review queue, review individual fields, then
materialize and verify the workbook. Complete each stage's file check before
advancing. The working JSON files below are execution artifacts that your
script must create and maintain, not descriptions to put in the final reply.

### 1. Execute a working extraction script

Use a terminal tool call to check `python3`, Tesseract, Pillow, pytesseract, and
the workbook writer. Create a script using those available tools and execute it
with `python3`. After a command error, issue the corrected command as an actual
tool call and inspect its result. Saying that a command will be run is not an
execution step. Implement the ledger, queue, protected-update, and workbook
functions in the actual script before starting bulk OCR. Inspect the script
to check that these functions are called on its executed path.

Create a working directory beside the prescribed workbook, for example
`ocr_work/`, containing `field_ledger.json` and `review_queue.json`. Initialize
one `date` and one `total_amount` record for every input filename, or load
existing records on resume. Execute this initialization, reopen both JSON
files, and print input count, field count, and state counts. Start bulk OCR
only after this check succeeds. A list of scalar workbook rows is not this
ledger.

Run long OCR scripts with `python3 -u` or flushed progress messages. Print the
filename and field/pass being processed before and after each expensive OCR
pass, and checkpoint after each image. For long terminal executions and waits,
use the tool's supported `timeout` parameter with a longer interval, such as
180 seconds, rather than repeatedly accepting its short default. A running
command without a new message is not proof of failure: inspect its progress
and checkpoint before another wait. Do not issue repeated identical short
empty waits or start a duplicate full-batch extraction while it is running.

### 2. Checkpoint field records after each image

Use `field_ledger.json` as the source of truth, keyed by filename and then
field. Each field record has this structure:

```json
{
  "value": null,
  "state": "unresolved",
  "first_pass_done": false,
  "candidates": [],
  "evidence": {
    "raw_text": null,
    "label": null,
    "bbox": null,
    "ocr_source": null
  },
  "confirmation_reason": null,
  "review_reason": "first pass pending",
  "changes": []
}
```

Populate candidates with the complete raw reading, label, source region, and
OCR variant. Use `candidate`, `unresolved`, and `confirmed` as distinct states.
Confirmation requires an explanation tying that complete reading to the actual
field. Non-empty values, valid formats, keyword scores, and repeated readings
alone leave a field unconfirmed. Set `first_pass_done` after recording that
field's initial observations and decision, even when its value is unresolved.
Save the records after each image, and save each subsequent review decision.
Each candidate must retain its complete raw reading, normalized proposal,
label, region coordinates, and OCR source. Preserve competing observations
instead of stopping when the first legal date or amount is found. Set
`confirmed` only when source evidence establishes both the complete reading
and its association with the requested field; explain that evidence in
`confirmation_reason`. Otherwise keep a proposed value as `candidate`, or
use `unresolved` when no defensible proposal exists.

First-pass completion check: reopen the ledger and verify that every required
field has `first_pass_done=true`, recorded observations or a missing-evidence
reason, and an explicit state. Print state counts and save the provisional
workbook from these records. Proceed to review even when every provisional
workbook cell is populated.

### 3. Select fields and build a review queue

For amounts, identify the final payable field after applicable tax, discount,
and rounding. Keep subtotal, tax charge, payment, change, item count, and
identifier candidates separate. A GST-inclusive final total remains eligible.
GST inclusion alone does not make an intermediate amount the final payable
amount: distinguish pre-rounding totals from the amount due after rounding.
Use displayed adjustments, their signs, and the receipt's arithmetic to link
these fields. A keyword score can propose a candidate, but cannot confirm it
or outrank a supported final-payable relationship. Queue label/value conflicts
and inconsistent amount relationships even when every number is well formed.
For cross-line fields, establish the label/value association from the layout
and surrounding text before choosing a complete number.

Preserve original punctuation. Apply character or separator corrections only
inside an identified numeric field with source evidence. Keep four-digit years
as four-digit years; interpret two-digit years and day/month order from receipt
context. A legal date or plausible monetary value is not proof of a correct
reading.

Build `review_queue.json` from the saved ledger, with one entry per filename
and field: `filename`, `field`, `reason`, `status`, and `outcome`. Initialize
required reviews as `pending`; store the review result in `outcome` and set
status to `reviewed` or `unresolved` after executing that review. Save the
queue whenever its membership or a review result changes.

Queue every missing, conflicting, ambiguous, or weak-fallback-dependent field,
including populated values produced by unsupported repairs. Every field not
yet confirmed enters the queue; confirmed fields also enter when new evidence
conflicts with them or an applicable parser change requires review. Queue
membership comes from evidence and extraction path, not an empty-cell check.
Do not accept agreement between OCR variants when they share an ambiguous
reading without checking the original labeled field. For each
queued field, save a crop containing its label and complete value, recognize
that crop, and preserve the crop coordinates and OCR observations, using
the original image and an appropriate OCR mode. Compare same-field readings
and use field meaning, arithmetic, and date context to decide. Inspect the
source region directly if the available tools support it and OCR remains
ambiguous. Record the decision; retain unresolved status when evidence is
insufficient. Clear evidence needs no additional voting.

Queue completion check: print each queued filename, field, reason, and final
review status. An empty queue is valid only when every field is confirmed
with supporting evidence and no unresolved conflict. A non-empty cell or
repeated OCR agreement alone cannot remove an entry. Keep unresolved entries
visible when source evidence remains insufficient.

### 4. Review locally and update incrementally

Reload the saved ledger and queue when reviewing or resuming. For each pending
entry, execute the local review, save its observations, and pass the proposal
through a single protected-update function. Save the resulting ledger and
queue before processing the next entry. Use the stored record when building
the workbook; a new full-batch extraction is not the resume path.

Implement the protected-update function with these branches:

1. An unconfirmed field accepts an evidence-backed proposal and retains the
   preceding candidate history.
2. A confirmed field with no new same-field contradiction keeps its value,
   state, evidence, and confirmation reason.
3. A contradiction or applicable parser change creates a review entry and
   keeps the saved confirmed value until that review resolves the conflict.
4. Change a confirmed value only after local review supplies stronger source
   evidence for that same field. Append old value, new value, supporting
   evidence, and correction reason to `changes`; preserve prior history.

Before bulk processing, exercise this function on synthetic records: a weak
different proposal preserves a confirmed record, stronger same-field evidence
can correct it with a change entry, and updating another field leaves the
confirmed record unchanged. Execute these checks, rather than merely naming
the function in comments. Confirmation protects an evidenced decision, not
the first plausible guess; contradictions always require review.

When changing a shared parser, load the saved ledger, identify the affected
fields, and generate separate proposals for those fields. Compare proposals
with the saved values, queue differences for local review, and apply reviewed
updates through the same function. Print the changed filename/field and
reason, and verify that unaffected confirmed records remain unchanged.

The following describes the required control flow; implement each helper in
the actual script, using the persistent files and update branches above:

```python
images = enumerate_input_images_sorted()
records = load_working_records_or_initialize(images)

for image in images:
    pending = [field for field in ("date", "total_amount")
               if not records[image.name][field]["first_pass_done"]]
    if not pending:
        continue  # resume from saved records; do not overwrite prior decisions
    print(f"first pass: {image.name}; fields={pending}", flush=True)
    observations = recognize_with_text_and_regions(image)  # log each OCR pass
    for field in pending:
        before = copy_field_record(records[image.name][field])
        proposal = select_with_field_evidence(observations, field)
        proposal["first_pass_done"] = True
        records[image.name][field] = protect_confirmed_field(before, proposal)
    save_working_records(records)  # checkpoint before processing the next image
    print(f"checkpoint saved: {image.name}", flush=True)

queue = fields_requiring_review(records)  # also includes non-empty weak guesses
for filename, field in queue:
    before = copy_field_record(records[filename][field])
    print(f"local review: {filename}; field={field}", flush=True)
    proposal = review_original_field_region(filename, field, before)
    proposal["first_pass_done"] = True
    records[filename][field] = protect_confirmed_field(before, proposal)
    save_working_records(records)

rows = materialize_prescribed_rows(records)  # confirmed values; null if unresolved
write_required_workbook(rows)
reopened_rows = reopen_required_workbook()
assert reopened_rows == rows
assert sorted_input_coverage_is_complete(reopened_rows, images)
report_confirmed_and_unresolved_counts(records)
```

`copy_field_record` preserves an independent snapshot of the existing value and
evidence. `protect_confirmed_field` keeps that snapshot unless a proposed change
has stronger evidence for the same field and records the reason for correction;
an unrelated rerun or parser preference cannot overwrite a confirmed result.
Retain confirmation and evidence when a new proposal adds no stronger support.
On resume, fields with a completed first pass go directly to this evidence-based
review path when needed, rather than being reinitialized by full-batch OCR.

An OCR/parser change updates affected fields through this review path. Preserve
unaffected confirmed fields and their evidence. If a shared parser changes,
compare affected proposals with saved records and apply only evidence-backed
updates. Rebuilding the workbook uses saved records; it does not rerun OCR for
the entire batch. Keep the working JSON outside the final workbook's schema.

### 5. Verify the actual deliverable before finishing

Execute the script and inspect its exit status. Reopen the actual target
workbook, verify the required sheets, columns, ordering and full input coverage,
and compare each saved field with its working record. Reopen the ledger and
queue too: verify required field coverage, supporting evidence for confirmed
records, and executed outcomes for review entries. Print the confirmed,
candidate, unresolved, and pending-review counts. Every non-confirmed field
must have a queue entry explaining its state, and no required review may
silently disappear. A record marked confirmed must carry its source evidence
and confirmation reason; a queued field must carry its review outcome.
Resolve outstanding fields where the source supports a decision. Otherwise use
the task's prescribed missing value and disclose the remaining uncertainty.
Invoke finish only after this execution and file verification, with an accurate
description of what was delivered.
