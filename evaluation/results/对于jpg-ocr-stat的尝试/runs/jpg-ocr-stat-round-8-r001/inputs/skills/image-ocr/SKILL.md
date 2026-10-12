---
name: image-ocr
description: Extract and validate text or structured fields from images with Tesseract, including auditable multi-pass adjudication for receipt dates and monetary totals
---

# Round 8 narrow override: rounded-total arithmetic consistency

This addendum is intentionally narrow. Preserve the existing receipt OCR/date
pipeline and the base Skill's semantic ranking for all fields unless the exact
condition below is met. In particular, do **not** broaden amount regexes, do not
change date convention logic, and do not replace an already-supported amount
with another generic TOTAL merely because it has more OCR votes.

## The defect being fixed

Full-page OCR can repeatedly misread one leading digit while still preserving
the label, decimal point, and remaining digits. This is especially dangerous
for labels such as `TOTAL AMT ROUNDED`, `TOTAL AMOUNT ROUNDED`, or an equivalent
final rounded-total line: semantic priority alone can make a wrong OCR token
outrank a nearby correctly read payable total.

Therefore, a multi-pass agreement on the same full-page OCR token is not enough
when the selected final amount is a **rounded-total** candidate whose value is
arithmetically inconsistent with the nearest preceding payable-total stage.

## Rounded-total invariant

When the selected amount comes from a line whose normalized label contains
`ROUND`, `ROUNDED`, or `ROUNDING` together with `TOTAL`/`AMOUNT`:

1. Locate the nearest preceding same-receipt payable-total candidate in the
   same local block. Legitimate examples include `TOTAL INCL. OF GST`,
   `TOTAL INCLUSIVE GST`, `TOTAL`, `TOTAL AMOUNT`, `TOTAL RM`, or another
   clearly final/pre-rounding payable total. A line that explicitly says
   `TOTAL ... INCL/INCLUSIVE ... GST` is a payable total and must **not** be
   rejected merely because it contains the token `GST`.
2. Compare the numeric values using `Decimal`.
3. Ordinary rounding is a small adjustment. If the rounded candidate differs
   from the preceding payable total by more than `1.00`, or differs in a
   leading digit / order of magnitude, mark the rounded value **disputed**.
   Do not accept it from full-page OCR consensus alone.
4. A larger difference may be accepted only if an explicit intervening
   discount, surcharge, tax, service charge, or other adjustment on the receipt
   numerically accounts for that difference. Never invent such an adjustment.

This rule is semantic/arithmetic, not filename-specific and not value-specific.

## Mandatory local adjudication for a disputed rounded total

For the disputed rounded-total field only:

- crop the exact numeric token tightly, retaining the decimal point;
- also crop a wider row/block that contains the rounded-total label and the
  preceding payable-total line;
- upscale the tight crop 3x-4x;
- run at least one original/non-binarized pass and two materially different
  image variants (for example autocontrast and threshold/sharpen), using a
  single-line PSM such as 7 for the tight token and PSM 6/11 for context;
- record each targeted read separately in the evidence ledger.

The rounded value is confirmed only if independent tight-token reads support it
and the wider crop confirms ownership by the rounded-total label. Repeated
full-page reads from transformations of the same source are supporting context,
not independent confirmation of a disputed leading digit.

If the targeted rounded-token OCR remains inconsistent but the immediately
preceding payable-total line is stable across independent OCR views and there
is no explicit intervening adjustment that changes the amount materially, use
the stable preceding payable amount as the final payable total rather than the
arithmetically impossible rounded OCR token.

## Regression guard

Do not apply this override to unrelated receipts/fields. Specifically:

- leave dates on the base pipeline;
- leave amounts whose selected label is not a rounded-total semantic on the
  base pipeline;
- do not introduce a blanket `amount >= threshold` re-OCR policy;
- do not loosen exclusions or semantic tiers globally;
- do not turn uncertainty elsewhere into null merely because this one rounded
  field needed extra adjudication.

After resolving the disputed field, perform the existing exact workbook
readback and completion checks.

# Round 5 mandatory receipt-field adjudication gate

For receipt OCR tasks that require an exact `date` and `total_amount` per image,
this block overrides weaker or more permissive advice below. Treat it as an
execution contract. Do not finish merely because an Excel file exists or every
row is non-null.

## A. Run bounded full-page OCR once, then cache it

1. Enumerate all receipt images in deterministic filename order.
2. For every image run a small fixed set of materially different full-page OCR
   passes (for example original/grayscale, contrast or sharpened, and thresholded;
   use useful PSM variants). Persist each pass's text **and token boxes** once.
3. Parse all field candidates from that cache. Never rerun the entire image set
   just because one parser rule changes.
4. After the cached full-page passes, additional OCR is allowed only for images
   and fields whose evidence is unresolved or conflicting.

Use `pytesseract.image_to_data(..., output_type=Output.DICT)` or an equivalent
box-producing API in addition to plain text OCR. Whole-page mean confidence is
not a valid reason to discard all candidates from another pass.

## B. Keep a field-level evidence ledger

For every `(filename, field)` pair, where `field` is `date` or `total_amount`,
persist candidate evidence with at least:

```
filename, field, pass_id, raw_line, normalized_label, semantic_class,
bbox_or_row_region, raw_candidate, normalized_candidate, confidence,
eligible, rejection_reason
```

The final selection must be reproducible from this ledger. Never reduce the
evidence to only `value -> number_of_passes`.

Two passes support one another only when they read the **same semantic field in
the same source region**. The same number occurring elsewhere on the receipt is
not supporting evidence. Group candidates by page-local row/box geometry and
field meaning before counting cross-pass agreement.

## C. Amount semantics: enumerate before selecting

For `total_amount`, collect all plausible amount candidates from every cached
pass before choosing a winner. Apply these rules in this order:

1. Reject lines containing task exclusion concepts such as `SUBTOTAL`,
   `SUB TOTAL`, `TAX`, `GST`, `SST`, `DISCOUNT`, `CHANGE`, or `CASH TENDERED`.
2. Reject product/table headings such as `QTY ITEM TOTAL`, `ITEM ... TOTAL`, or
   another line where `TOTAL` is a column header rather than a payable field.
3. Prefer explicit final-payment semantics (`GRAND TOTAL`, `TOTAL RM`,
   `TOTAL AMOUNT`, `TOTAL DUE`, `AMOUNT DUE`, `BALANCE DUE`, `NETT TOTAL`,
   `NET TOTAL`) over a generic `TOTAL` occurrence.
4. Distinguish intermediate sales totals from a later adjustment/rounding/final
   payable stage. A `TOTAL SALES` or similar earlier accounting stage must not
   outrank a later clearly final/adjusted payable amount merely because it is
   easier to OCR or appears in more passes.
5. Never select `amounts[-1]`, the largest amount, the most frequent number, or
   the first legal match as a substitute for semantic adjudication.

### Safe next-line fallback

Use the task's next-line fallback only if the current line is a **standalone
payable-field label**. The next line must be locally adjacent, aligned with the
field's value region, and contain only a plausible currency/value token rather
than an item description, quantity, unit price, tendered amount, change, or a
new field label. Record the label/value boxes proving the pairing.

## D. Decimal placement is evidence, not formatting

Do not let numeric whitelists or normalization silently destroy monetary
punctuation. A digits-only pass that reads `1000` cannot by itself prove whether
the source is `1000`, `100.0`, or `10.00`. It may support the digit sequence,
but decimal placement must be confirmed by a pass/crop that preserves
punctuation or by clear same-region visual/OCR evidence.

Keep the raw candidate string. Remove thousands separators only after the
decimal mark is established. Use `Decimal` for normalization and format the
accepted final amount to exactly two decimal places only **after** the source
value is adjudicated. Never append/remove digits merely to make a plausible
currency value.

## E. Date parsing must preserve token order

Collect every date candidate across passes before selecting. Do not return the
first syntactically valid date and do not let a parser silently choose MDY/DMY
for an ambiguous slash date.

For each candidate keep the raw text and component order. Determine the date
convention from explicit labels/context and, where needed, unambiguous dates or
consistent formatting evidence. Once a convention is established for that
receipt/context, apply it explicitly. A disagreement in day, month, **or year**
between passes makes the field disputed and triggers targeted OCR.

## F. Every disagreement must trigger targeted OCR

A field is disputed if any of these holds:

- same-region passes produce different normalized values;
- only one usable pass supports a candidate;
- two different semantic candidates remain eligible;
- decimal placement differs or disappears between passes;
- a date component differs between passes;
- a next-line fallback lacks strong local pairing evidence;
- OCR confidence/fragmentation makes any digit uncertain.

For every disputed field, stop broad OCR and make targeted crops around the
field's label/value row. Use both:

- a **tight value crop** to improve digit recognition; and
- a **wider context crop** that retains the label and neighboring lines so the
  number's semantic ownership is visible.

Upscale the crops (2x minimum; 3x/4x when useful), try materially different
preprocessing, and use appropriate PSMs such as 6/7/11. A numeric whitelist is
an auxiliary pass, not authoritative evidence for punctuation. Add every
targeted result to the same ledger.

Printing a disagreement table is not resolution. Each disputed ledger row must
cause an actual targeted retry and finish with a winner or an explicit reject
reason for each competing candidate.

## G. Blocking pre-write audit

Before creating `stat_ocr.xlsx`, build one compact final audit row per input
image containing:

```
filename | selected date | date evidence regions/passes |
selected total | total evidence regions/passes | rejected alternatives | status
```

Programmatically enforce at least:

```python
assert audit_filename_set == input_filename_set
assert unresolved_field_count == 0
assert single_pass_non_null_winner_count == 0
assert cross_region_consensus_count == 0
assert unresolved_competing_candidate_count == 0
assert unsafe_next_line_winner_count == 0
```

If one fails, continue **only** with the unresolved images/fields. Do not rerun
already-resolved images and do not write the final workbook yet.

## H. Exact artifact contract and readback

After the field audit passes:

1. create exactly one sheet named `results`;
2. write exactly the columns `filename`, `date`, `total_amount`;
3. sort data rows by filename and include exactly one row for every input image;
4. write dates as ISO `YYYY-MM-DD` strings (or null only when genuinely
   unresolved according to the task contract);
5. write accepted monetary values as strings with exactly two decimal places;
6. save to the exact required path `/app/workspace/stat_ocr.xlsx`;
7. reopen that saved workbook and read every cell back;
8. compare the readback programmatically to the adjudicated audit rows and the
   exact sheet/header/order constraints.

Only the reopened workbook matching the adjudicated evidence is completion.

## I. Completion-budget discipline

Once a `(filename, field)` has strong same-region evidence, freeze it. Spend
remaining OCR/tool calls only on disputed fields. The intended workflow is:

`bounded cached batch -> field ledger -> targeted retries -> audit -> one write -> readback`.

Do not regress to repeated whole-dataset OCR commands during parser iteration or
final workbook creation.

# Image OCR Skill

## Purpose
This skill enables accurate text extraction from image files (JPG, PNG, etc.) using Tesseract OCR via the `pytesseract` Python library. It is suitable for scanned documents, screenshots, photos of text, receipts, forms, and other visual content containing text.

## Blocking Evidence Gate for Exact Structured Fields

When OCR values will be written into a table, database, or other artifact that
requires exact dates or monetary amounts, the following rules are mandatory.
They are execution requirements, not optional quality suggestions. Do not
materialize the artifact or finish the task until the programmatic gate passes.

1. **Verify every resolved field independently** - Every non-null date and
   monetary amount must have the same normalized value, field meaning, and
   supporting source region in at least two materially different OCR passes.
   Change preprocessing, segmentation mode, scale, or crop; repeating the same
   pixels and configuration is not independent evidence. A syntactically valid
   value from one pass remains an unverified candidate.
2. **Collect before selecting** - Complete the required passes and enumerate all
   field candidates before choosing a winner. Never select the first legal date,
   first keyword match, first non-null pass, largest number, or final numeric
   token merely because it is available.
3. **Escalate every disagreement** - If independent passes disagree in any date
   component or monetary digit, run at least one targeted crop or alternative
   segmentation pass over that field. If bounded retries still do not establish
   independent agreement within the correct semantic class, emit the task's
   null/error representation instead of guessing.
4. **Use safe line pairing** - A next-line amount is eligible only when the
   current line is a standalone target-field label and spatial evidence or a
   targeted crop confirms that the adjacent line is its value. The adjacent line
   must contain only currency/value tokens. Reject it if it contains an item,
   description, quantity, price, cash received, tendered, change, payment, or
   another field label.
5. **Adjudicate semantics before agreement** - Apply the task's exclusions and
   keyword groups before counting cross-pass agreement. Within the same allowed
   keyword group, a final adjusted, after-adjustment, rounded, amount-due,
   balance-due, or grand-total stage outranks an earlier sales total and any
   tendered/payment value. For dates, collect every date candidate across the
   receipt and all passes; use the requested field meaning, label proximity,
   region, and cross-pass agreement rather than returning the first valid date.
6. **Persist the candidate audit first** - For every input and required field,
   save the pass identifier/configuration, raw supporting line, location or crop,
   normalized candidate, semantic class, eligibility or rejection reason,
   selected winner, and the independent passes supporting it. Record unresolved
   fields as well as successful fields.
7. **Run a blocking completion audit** - The program must fail or continue OCR
   unless all of these conditions hold:
   - every input has an audit record for every required field;
   - every non-null winner has at least two independent supporting passes;
   - every competing candidate has a resolution or rejection reason;
   - every next-line winner has verified label-value pairing; and
   - the reopened final artifact exactly matches the audited winners.

At minimum, make these invariants explicit in executable checks:

```python
assert audit_record_count == input_count * required_field_count
assert single_pass_winner_count == 0
assert unresolved_competing_candidate_count == 0
assert unsafe_next_line_winner_count == 0
assert artifact_rows == audited_rows
```

A schema check, non-null check, or spot-check does not satisfy this gate. If any
assertion fails, resume targeted OCR or adjudication; the task is not complete.

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

### Checkpointed Batch OCR

For a batch whose OCR text feeds later parsing or file generation, use a
checkpointed pipeline with observable completion criteria:

1. **Inventory** - Create one deterministic, sorted list of inputs and a status
   record for every filename before OCR starts.
2. **Acquire and checkpoint** - Run one baseline OCR pass per image. Immediately
   append its raw text, OCR configuration, warnings, and terminal status to a
   durable JSON/JSONL cache. A resumed run processes only records without a
   terminal status.
3. **Parse the cache** - Treat cached OCR observations as the input to field
   extraction. Parser, regular-expression, priority, and formatting changes rerun
   against the cache rather than triggering another full OCR batch.
4. **Escalate selectively** - Send only images with missing, conflicting, or
   structurally invalid required fields to a bounded multi-pass retry. Append every
   retry observation and its provenance to the same cache.
5. **Measure progress** - After each image, report the completed count and current
   filename. Repeated polls with no new output and no increase in completed records
   trigger termination of that attempt followed by resume from the checkpoint.
6. **Materialize separately** - Build the requested artifact from normalized cached
   records in a short, deterministic command. Represent unresolved fields using the
   task's required null or error value so one image cannot block batch delivery.
7. **Gate completion** - Finish only after every inventoried input has a terminal
   status and the exact requested artifact exists, reopens successfully, and meets
   its required schema and ordering.


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

For exact structured dates or monetary amounts, run at least two independent OCR
passes for every required field even when the baseline looks syntactically valid.
For ordinary free-text extraction, additional passes may remain selective. Preserve
each pass as a separate observation so downstream extraction can resolve fields
independently:

1. **Try a bounded set of PSM modes** - Different page segmentation modes work
   better for different layouts (for example, `--psm 6` for blocks, `--psm 4`
   for columns, and `--psm 11` for sparse text).
2. **Try a bounded set of preprocessing variants** - Run OCR on selected
   preprocessed versions of the difficult image.
3. **Keep provenance** - Store the text together with its preprocessing variant
   and PSM mode. Preserve line or bounding-box context when it is available.
4. **Resolve per field** - Select each target field using field-local evidence:
   label proximity, required keyword priority, valid format and range, layout
   context, and agreement across passes. Whole-page average confidence is a broad
   quality signal; it is not a valid reason to select one pass for every field.
5. **Expose unresolved conflicts** - When evidence cannot distinguish competing
   candidates, use the task's specified null/error representation and record the
   conflict instead of inventing a value or concatenating unrelated pass text.

```python
def multi_pass_ocr(image_path):
    """Return bounded OCR observations with their provenance."""
    img = Image.open(image_path)
    gray = ImageOps.grayscale(img)

    # Generate preprocessing variants
    variants = [
        ("autocontrast", ImageOps.autocontrast(gray)),
        ("inverted", ImageOps.invert(ImageOps.autocontrast(gray))),
        ("sharpened", gray.filter(ImageFilter.SHARPEN)),
    ]

    # PSM modes to try
    psm_modes = ['--psm 6', '--psm 4', '--psm 11']

    observations = []
    for variant_name, variant in variants:
        for psm in psm_modes:
            try:
                text = pytesseract.image_to_string(variant, config=psm)
                if text.strip():
                    observations.append({
                        "variant": variant_name,
                        "psm": psm,
                        "text": text,
                    })
            except Exception:
                pass

    return observations
```

Parse these observations into per-field candidates and retain the winning
candidate's provenance. This approach improves extraction for receipts, faded
documents, and images with varying quality without allowing a high-confidence
region elsewhere on the page to override the evidence for a target field.

### Semantic Adjudication for Monetary Totals

When several OCR lines contain plausible monetary totals, determine the target
field from label semantics before applying confidence, frequency, magnitude, or
page-position heuristics:

1. **Normalize labels before matching** - Compare labels case-insensitively and
   tolerate OCR changes in whitespace, punctuation, and hyphenation. Keep the
   original line and its coordinates as provenance.
2. **Apply task exclusions as hard constraints** - If the task excludes labels
   such as subtotal, tax, GST, discount, change, or tendered cash, remove those
   candidates before ranking. A line containing a preferred word such as
   `TOTAL` does not override an exclusion on the same line.
3. **Prefer the final payable stage within the allowed keyword group** - First
   honor the task's stated keyword-group order. Within the selected group, an
   explicitly adjusted, after-adjustment, rounded, amount-due, balance-due, or
   grand total supersedes an earlier sales total or intermediate calculation.
   Preserve the document's calculation sequence when valid labels conflict.
4. **Do not let repetition decide semantics** - Cross-pass agreement can
   support an already valid candidate, but a repeated subtotal or tax-summary
   value must not outrank a single value attached to the correct final-total
   label. Frequency is at most a tie-breaker within the same semantic class.
5. **Do not select by largest or last number alone** - A line can contain a
   taxable base, tax amount, paid amount, or change alongside a total label.
   Associate the value with its label using line structure and bounding-box
   proximity; unresolved multi-number lines require targeted re-OCR or a null
   result rather than an arbitrary maximum or final token.
6. **Audit the winner before materialization** - Record the winning value,
   normalized label, original OCR line, pass provenance, rejected competing
   candidates, and the rule that resolved the conflict. Recheck any winner
   whose supporting line violates an exclusion or belongs to an earlier stage
   of the receipt calculation.

### Implementation Gate for Receipt-Total Parsers

The preceding semantic rules must be visible in the implemented parser and its
saved evidence. A generic keyword loop or a final workbook schema check is not
an acceptable substitute. Apply this gate whenever OCR text contains more than
one occurrence of a word such as `TOTAL` or `AMOUNT`:

1. **Enumerate before choosing** - Scan the complete receipt observation and
   collect every plausible monetary candidate before returning a value. Never
   return on the first keyword match. A later final-payment line must remain
   eligible to supersede an earlier table heading or intermediate calculation.
2. **Reject table headings explicitly** - Treat lines containing structural
   column terms such as `QTY`, `ITEM`, `DESCRIPTION`, `UNIT PRICE`, or `PRICE`
   as table headings unless the amount is explicitly attached to a standalone
   payable label. The presence of the token `TOTAL` in a heading does not make
   the following item row a receipt total.
3. **Restrict next-line fallback** - Read an amount from the following line only
   when the label line is an independent payable-field label after normalized
   punctuation and whitespace are removed, and the next line contains only the
   associated currency/value tokens. Do not use this fallback for column
   headings, prose, item descriptions, cash received, tendered, change, payment,
   or lines that mix unrelated fields.
4. **Assign a semantic stage** - Store a semantic class for each eligible
   candidate, such as final adjusted or rounded payable, amount or balance due,
   grand total, generic total, or earlier sales/intermediate total. Apply the
   task's exclusions first, then choose the most final eligible calculation
   stage. OCR frequency is allowed only as a last tie-breaker among candidates
   in the same semantic class.
5. **Preserve candidate evidence** - For every candidate retain the filename,
   OCR pass, raw line, normalized label, line or bounding-box location, parsed
   amount, semantic class, and any rejection reason. If the parser cannot
   explain why the winner outranks each competing candidate, the field remains
   unresolved and receives targeted OCR instead of a guessed value.
6. **Validate behavior, not only shape** - Before writing the final artifact,
   inspect the candidate audit for every input with competing totals. Confirm
   that no excluded candidate, table-heading fallback, first-match shortcut, or
   cross-class frequency vote selected the winner. A schema/order check alone
   does not satisfy completion.

A compliant selection routine follows this structure:

```python
candidates = collect_all_candidates(observations)
eligible = [candidate for candidate in candidates if not candidate.excluded]

if not eligible:
    winner = None
else:
    best_stage = min(candidate.semantic_rank for candidate in eligible)
    finalists = [
        candidate for candidate in eligible
        if candidate.semantic_rank == best_stage
    ]
    # Agreement may break a tie only after semantic filtering.
    winner = resolve_same_stage(finalists)

save_candidate_audit(candidates, winner)
```

Do not replace this structure with `first match`, `last number`, `largest
number`, or unrestricted majority-vote shortcuts.


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
- [ ] Every batch input has a terminal status in the checkpoint
- [ ] Required fields were resolved independently with candidate provenance
- [ ] Every non-null exact date and monetary amount is supported by at least two
      materially different OCR passes over the same source region
- [ ] Every cross-pass disagreement triggered targeted OCR and semantic review
- [ ] Task-defined monetary exclusions were applied before candidate ranking
- [ ] Monetary conflicts were resolved by label semantics and calculation stage,
      not by frequency, magnitude, or last-number shortcuts
- [ ] The parser scanned the complete observation before selecting a monetary
      value and rejected table-heading and unsafe next-line fallbacks
- [ ] A candidate audit records the winner, semantic stage, competing values,
      and rejection reasons for every receipt with conflicting totals
- [ ] Missing or conflicting fields use the task's specified null/error value
- [ ] The exact requested final artifact exists, reopens, and has the required schema


## Limitations

- Tesseract works best with printed text; handwriting recognition is limited
- Accuracy decreases with decorative fonts, artistic text, or extreme stylization
- Mathematical equations and special notation may not extract accurately
- Redacted or watermarked text cannot be recovered
- Severe image degradation (blur, noise, low resolution) reduces accuracy
- Complex multi-column layouts may require custom PSM configuration


## Version History

- **1.1.0** (2026-09-12): Added a blocking multi-pass evidence and audit gate for exact structured date and monetary extraction
- **1.0.0** (2026-01-13): Initial release with Tesseract/pytesseract OCR
