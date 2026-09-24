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
```python
import pytesseract
from PIL import Image, ImageFilter, ImageOps
import re
import os
```
## Critical Workflow Rules
### Always run the script after editing it
After every edit to the extraction script, immediately re-run `python3 extract.py` and verify the on-disk xlsx before considering the task done. The xlsx must reflect the latest code. Do not end the session on an edit — end on a successful run whose output you have inspected.
### Preprocessing variants for receipts
For OCR of receipts, use multiple preprocessing variants and aggregate results. A robust default set (in order):
1. Original (default PSM)
2. Grayscale + autocontrast, `--psm 6`
3. 2x upscale grayscale + autocontrast, `--psm 6`
4. 3x upscale grayscale + autocontrast + sharpen, `--psm 4`
The 3x upscale + psm 4 variant is specifically effective for fragmented "Grand Total" lines that other variants miss.
```python
def ocr_variants(image_path):
    img = Image.open(image_path)
    gray = ImageOps.autocontrast(ImageOps.grayscale(img))
    up2 = gray.resize((gray.width*2, gray.height*2), Image.LANCZOS)
    up3 = gray.resize((gray.width*3, gray.height*3), Image.LANCZOS).filter(ImageFilter.SHARPEN)
    return [
        pytesseract.image_to_string(img),
        pytesseract.image_to_string(gray, config='--psm 6'),
        pytesseract.image_to_string(up2, config='--psm 6'),
        pytesseract.image_to_string(up3, config='--psm 4'),
    ]
```
## Receipt Total Extraction Strategy
### Keyword tiers (most-specific first)
1. `GRAND TOTAL`
2. `TOTAL RM`, `TOTAL: RM`
3. `TOTAL AMOUNT`
4. `TOTAL`, `AMOUNT`, `TOTAL DUE`, `AMOUNT DUE`, `BALANCE DUE`, `NETT TOTAL`, `NET TOTAL`
### Exclusion patterns (skip these lines entirely)
`SUBTOTAL`, `SUB TOTAL`, `TAX`, `GST`, `SST`, `DISCOUNT`, `CHANGE`, `CASH TENDERED`, `CASH RECEIVED`, `CASH PAYMENT`, `EXCLUDING`, `TOTAL GST`, `TOTAL TAX`, `TOTAL SST`, `TOTAL ITEMS`, `TOTAL QTY`, `TOTAL SAVINGS`, `ROUNDED`, `ROUNDING`, `DESCRIPTION`, table header patterns like `QTY ... PRICE ... AMOUNT`, and payment card names like `VISA`, `MASTERCARD`.
Critically, `ROUNDED`/`ROUNDING` MUST be excluded — lines such as "Total Amt Rounded 702.00" are OCR-garbled rounding lines, not the true total, and will beat the true total in voting if not excluded.
### Number parsing
- Strict 2-decimal regex: `r'(\d{1,3}(?:,\d{3})*|\d+)\.\d{2}\b'`
- Strip commas before converting to float.
- On a keyword line, take the **last** matching number.
- Two-line fallback: only when the keyword line itself has **no digits**, look at the next non-empty line and take its last number.
### Aggregating across variants
1. Collect (tier, value) candidates from all variants.
2. Pick the lowest tier index present.
3. Within that tier, take the majority value; on ties, prefer the value produced by the highest-index variant (upscaled variants are more trustworthy than the default pass).
## Date Extraction
Handle these formats and normalize to `YYYY-MM-DD`:
- `DD/MM/YYYY` or `DD-MM-YYYY`
- `DD/MM/YY` → prepend `20`
- `YYYY/MM/DD` or `YYYY-MM-DD`
## Steps
1. Enumerate image files under the input directory (sorted).
2. For each image, run all 4 OCR variants above.
3. From each variant's text, apply keyword-tier matching with exclusions, using strict 2-decimal regex and the digit-less two-line fallback.
4. Aggregate candidates across variants using the tier + majority + upscale-preference rule.
5. Extract date using the multi-format normalizer.
6. Write results to xlsx (see `xlsx` skill), sorted by filename, one sheet `results`, columns `filename,date,total_amount`. Missing extractions become `None`.
7. **Run `python3 extract.py`** and inspect the printed rows plus the saved xlsx before finishing.
## Expected Result
An xlsx at the specified path with exactly one sheet `results` and three columns, one row per input image, ordered by filename. Every row reflects the most recent script execution.
