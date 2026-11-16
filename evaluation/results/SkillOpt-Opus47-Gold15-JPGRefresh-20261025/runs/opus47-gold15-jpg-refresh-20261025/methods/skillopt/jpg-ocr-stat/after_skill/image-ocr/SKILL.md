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



## Receipt Field Extraction (Date + Total)

This section provides a drop-in recipe for extracting the transaction `date` (ISO `YYYY-MM-DD`) and `total_amount` (two-decimal string, e.g., `47.70`) from scanned receipt JPGs. Use this when the task is specifically receipt extraction; the generic OCR sections above do not implement the receipt-specific heuristics (tiered keywords, exclusions, rounding-wins, split-line fallback, date disambiguation).

### (A) Multi-variant preprocessing

Run OCR on at least four variants and aggregate text per variant:

1. Original image, `--psm 6`
2. Grayscale + `ImageOps.autocontrast`, `--psm 6`
3. 2x LANCZOS upscale of variant 2, `--psm 6`
4. 3x LANCZOS upscale of variant 2, `--psm 4`
5. (Optional) Binarized/inverted upscale, `--psm 6` or `--psm 11` for faded scans

### (B) Tiered total keywords and exclusions

```python
TIERS = [
    ["GRAND TOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    ["TOTAL", "AMOUNT", "TOTAL DUE", "AMOUNT DUE", "BALANCE DUE",
     "NETT TOTAL", "NET TOTAL", "ROUNDED TOTAL", "TOTAL ROUNDED",
     "TOTAL AFTER ROUNDING", "TOTAL INCL GST", "TOTAL RM INCLUDING GST"],
]

EXCLUSIONS = [
    "SUBTOTAL", "SUB TOTAL", "SUB-TOTAL",
    "TAX", "GST", "SST",
    "DISCOUNT", "CHANGE",
    "CASH TENDERED", "CASH RECEIVED", "CASH PAYMENT",
    "VISA", "MASTERCARD", "DEBIT", "CREDIT", "CARD", "PAYMENT",
    "ROUNDING ADJ", "ROUNDING ADJUSTMENT",
    "TOTAL GST", "TOTAL TAX", "TOTAL SST", "GST TOTAL", "TAX TOTAL",
    "TOTAL ITEMS", "TOTAL ITEM(S)", "ITEM COUNT",
    "TOTAL QTY", "TOTAL QUANTITY", "TOTAL SAVINGS",
    "EXCLUDING", "EXCL GST", "AMT EXCL",
    "DESCRIPTION", "QTY PRICE AMOUNT", "PRICE AMOUNT",
    "AVERAGE", "PAX",
]
```

IMPORTANT distinctions:
- `TOTAL GST` / `GST TOTAL` → EXCLUDE (that's the tax amount).
- `TOTAL INCL GST` / `TOTAL (INCLUSIVE OF GST)` → INCLUDE (that's the invoice total).
- Match exclusions BEFORE tier matches on the same line.

### (C) GST/TAX SUMMARY section cutoff

Once a line matches `GST SUMMARY`, `TAX SUMMARY`, or `TAX CODE`, treat ALL subsequent lines in that variant as excluded for total selection. These sections commonly repeat totals in a tax-breakdown table and must not be selected.

### (D) Amount regex (strict two-decimal, thousands-separator aware)

```python
AMOUNT_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})(?![\w.\d])")

def to_amount(tok: str) -> float:
    return float(tok.replace(",", ""))

def fmt_amount(v: float) -> str:
    return f"{v:.2f}"  # always two decimals
```

### (E) OCR confusion repair (applied inside numeric-looking tokens only)

- `O`, `o`, `Q` → `0`
- `l`, `I`, `|` → `1`
- `S` → `5`
- `B` → `8`
- `u` → `0`
- Standalone `RN` → `RM`
- `:` → `.` only inside amount-shaped tokens (e.g., `23:25` → `23.25`)
- Collapse `NN NN` at end of a keyword line into `NN.NN` (e.g., `TOTAL 23 25` → `TOTAL 23.25`)

Apply these BEFORE regex matching, but only inside candidate numeric tokens — do not rewrite whole lines, or you'll corrupt keyword matching (e.g., `TOTAL` must stay `TOTAL`, not `T0TAL`).

### (F) Per-variant selection

For each OCR variant:

1. Split into lines; strip.
2. Apply the GST/TAX SUMMARY cutoff.
3. For each non-excluded line, check tiers from lowest index (most specific) to highest.
4. If a tier keyword matches:
   - Extract all 2-decimal amounts on the SAME line via `AMOUNT_RE`; take the LAST one as the candidate.
   - If the keyword line has NO digits at all, fall back to the LAST 2-decimal amount on the next non-empty, non-excluded line (look at most 2 lines ahead). This handles split-line receipts.
   - If the keyword line has PARTIAL/garbled digits (digits present but no clean 2-decimal match), DO NOT fall through — otherwise you'll leak Visa/Cash amounts from below.
5. Record `(tier_index, value, line_index, variant_id)`.

### (G) Cross-variant final selection

From all collected candidates across all variants:

1. Pick the LOWEST `tier_index` that has any candidate (most specific tier wins).
2. Within that tier, prefer values corroborated by:
   - Appearance in multiple variants (cross-variant frequency vote), OR
   - A matching 2-decimal amount on a `Subtotal`/`Payment`/`Cash`/`Rounded Total` line of the same receipt.
3. Tie-break by LAST occurrence in the receipt — this encodes the "final rounded total wins" rule.
4. As a last resort, naive majority vote across variants.

**Worked example (rounding-wins):**

```
...
Total (Inclusive of GST): 23.26
Rounding Adj:              -0.01
TOTAL:                      23.25
```

Both `23.26` and `23.25` are tier-3 candidates. The LAST occurrence (`23.25`) wins → output `"23.25"`.

### (H) Date extraction

Try regexes in this order, preferring matches on lines containing `Date`, `DATE`, `Tarikh`, or `INV`:

1. `DD[/-.]MM[/-.]YYYY`
2. `DD[/-.]MM[/-.]YY`  → expand `yy` as `20yy` if `yy <= 49` else `19yy` (or simply `2000+yy` for modern receipts)
3. `YYYY[/-.]MM[/-.]DD`
4. `DD Mon YYYY` (e.g., `09 Mar 2018`)

Ambiguity rules:
- Default DD/MM/YYYY (Malaysian/SEA convention) unless the first field > 12, which forces MM/DD/YYYY.
- Example: `09/03/2018` → `2018-03-09` (NOT `2018-08-09`).

Validation: `1 <= d <= 31`, `1 <= mo <= 12`, `2000 <= y <= 2099`. On failure, try single-digit OCR-confusion swaps on month then day (`6↔0`, `8↔3`, `1↔7`, `5↔6`) and revalidate. Emit ISO `YYYY-MM-DD` or `None`.

### (I) Reference implementation

```python
import os, re, glob
from collections import Counter
from PIL import Image, ImageOps
import pytesseract
import pandas as pd

AMOUNT_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})(?![\w.\d])")

TIERS = [
    ["GRAND TOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    ["TOTAL", "AMOUNT", "TOTAL DUE", "AMOUNT DUE", "BALANCE DUE",
     "NETT TOTAL", "NET TOTAL", "ROUNDED TOTAL", "TOTAL ROUNDED",
     "TOTAL AFTER ROUNDING", "TOTAL INCL GST"],
]

EXCLUSIONS = [
    "SUBTOTAL","SUB TOTAL","SUB-TOTAL","TAX","GST","SST","DISCOUNT","CHANGE",
    "CASH TENDERED","CASH RECEIVED","CASH PAYMENT","VISA","MASTERCARD",
    "DEBIT","CREDIT","CARD","PAYMENT","ROUNDING ADJ","ROUNDING ADJUSTMENT",
    "TOTAL GST","TOTAL TAX","TOTAL SST","GST TOTAL","TAX TOTAL",
    "TOTAL ITEMS","ITEM COUNT","TOTAL QTY","TOTAL QUANTITY","TOTAL SAVINGS",
    "EXCLUDING","EXCL GST","AMT EXCL","DESCRIPTION","QTY PRICE AMOUNT",
    "PRICE AMOUNT","AVERAGE","PAX",
]
SUMMARY_CUTOFF = ("GST SUMMARY", "TAX SUMMARY", "TAX CODE")

def _variants(path):
    img = Image.open(path)
    gray = ImageOps.autocontrast(ImageOps.grayscale(img))
    w, h = gray.size
    up2 = gray.resize((w*2, h*2), Image.LANCZOS)
    up3 = gray.resize((w*3, h*3), Image.LANCZOS)
    return [
        (img, "--psm 6"),
        (gray, "--psm 6"),
        (up2, "--psm 6"),
        (up3, "--psm 4"),
    ]

def _ocr_lines(path):
    out = []
    for v, cfg in _variants(path):
        try:
            txt = pytesseract.image_to_string(v, config=cfg)
            out.append([ln.strip() for ln in txt.splitlines()])
        except Exception:
            out.append([])
    return out

def _is_excluded(line_upper):
    # 'TOTAL INCL GST' / 'TOTAL (INCLUSIVE OF GST)' must NOT be excluded by 'GST'
    if "INCL" in line_upper and "GST" in line_upper and "TOTAL" in line_upper:
        return False
    return any(kw in line_upper for kw in EXCLUSIONS)

def _tier_of(line_upper):
    for i, kws in enumerate(TIERS):
        for kw in kws:
            if kw in line_upper:
                return i
    return None

def _amounts(line):
    return AMOUNT_RE.findall(line)

def _candidates_from_lines(lines):
    cands = []  # (tier, value, line_idx)
    cutoff = False
    for i, ln in enumerate(lines):
        up = ln.upper()
        if any(s in up for s in SUMMARY_CUTOFF):
            cutoff = True
        if cutoff or not ln:
            continue
        if _is_excluded(up):
            continue
        t = _tier_of(up)
        if t is None:
            continue
        amts = _amounts(ln)
        if amts:
            cands.append((t, float(amts[-1].replace(",","")), i))
            continue
        has_digit = any(c.isdigit() for c in ln)
        if has_digit:
            continue  # partial/garbled — do not fall through
        for j in range(i+1, min(i+3, len(lines))):
            nxt = lines[j]
            if not nxt or _is_excluded(nxt.upper()):
                continue
            nxt_amts = _amounts(nxt)
            if nxt_amts:
                cands.append((t, float(nxt_amts[-1].replace(",","")), j))
                break
    return cands

def _select_total(all_variant_lines):
    all_cands = []  # (tier, value, line_idx, variant_id)
    for vid, lines in enumerate(all_variant_lines):
        for t, v, li in _candidates_from_lines(lines):
            all_cands.append((t, v, li, vid))
    if not all_cands:
        return None
    best_tier = min(c[0] for c in all_cands)
    pool = [c for c in all_cands if c[0] == best_tier]
    freq = Counter(round(c[1], 2) for c in pool)
    # prefer most frequent across variants; tie-break by LAST line index
    max_f = max(freq.values())
    top_vals = {v for v, f in freq.items() if f == max_f}
    best = max((c for c in pool if round(c[1], 2) in top_vals), key=lambda c: c[2])
    return f"{best[1]:.2f}"

_DATE_RES = [
    (re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})\b"), "dmy2"),
    (re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})\b", re.I), "dmony"),
]
_MONTHS = {m:i+1 for i,m in enumerate(["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"])}

def _valid(y, mo, d):
    return 2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31

def _try_swap(y, mo, d):
    swaps = {"6":"0","0":"6","8":"3","3":"8","1":"7","7":"1","5":"6","6":"5"}
    for field in ("mo","d"):
        val = mo if field == "mo" else d
        s = str(val)
        for i, ch in enumerate(s):
            if ch in swaps:
                cand = int(s[:i] + swaps[ch] + s[i+1:])
                ny, nmo, nd = (y, cand, d) if field == "mo" else (y, mo, cand)
                if _valid(ny, nmo, nd):
                    return ny, nmo, nd
    return None

def _extract_date(all_variant_lines):
    labeled = []
    unlabeled = []
    for lines in all_variant_lines:
        for ln in lines:
            is_label = any(k in ln for k in ("Date","DATE","Tarikh","INV"))
            (labeled if is_label else unlabeled).append(ln)
    for pool in (labeled, unlabeled):
        for ln in pool:
            for rx, kind in _DATE_RES:
                m = rx.search(ln)
                if not m: continue
                try:
                    if kind == "dmy":
                        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                        d, mo = (a, b) if a > 12 or b <= 12 else (b, a)
                    elif kind == "ymd":
                        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    elif kind == "dmy2":
                        a, b, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
                        y = 2000 + yy if yy <= 49 else 1900 + yy
                        d, mo = (a, b) if a > 12 or b <= 12 else (b, a)
                    else:  # dmony
                        d = int(m.group(1)); mo = _MONTHS[m.group(2).lower()[:3]]; y = int(m.group(3))
                    if _valid(y, mo, d):
                        return f"{y:04d}-{mo:02d}-{d:02d}"
                    swapped = _try_swap(y, mo, d)
                    if swapped:
                        y, mo, d = swapped
                        return f"{y:04d}-{mo:02d}-{d:02d}"
                except Exception:
                    continue
    return None

def extract_receipt_fields(image_path):
    lines_per_variant = _ocr_lines(image_path)
    return {
        "date": _extract_date(lines_per_variant),
        "total_amount": _select_total(lines_per_variant),
    }

def process_receipts_to_xlsx(img_dir, out_xlsx):
    rows = []
    for p in sorted(glob.glob(os.path.join(img_dir, "*.jpg"))):
        fn = os.path.basename(p)
        try:
            r = extract_receipt_fields(p)
        except Exception:
            r = {"date": None, "total_amount": None}
        rows.append({"filename": fn, "date": r["date"], "total_amount": r["total_amount"]})
    df = pd.DataFrame(rows, columns=["filename","date","total_amount"])
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="results", index=False)
```

### (J) Output contract

- `total_amount`: two-decimal string (e.g., `"47.70"`) or `None` on failure.
- `date`: ISO `YYYY-MM-DD` string or `None` on failure.
- Excel: single sheet `results`, columns `filename,date,total_amount`, rows sorted by filename, no extra sheets/columns.
