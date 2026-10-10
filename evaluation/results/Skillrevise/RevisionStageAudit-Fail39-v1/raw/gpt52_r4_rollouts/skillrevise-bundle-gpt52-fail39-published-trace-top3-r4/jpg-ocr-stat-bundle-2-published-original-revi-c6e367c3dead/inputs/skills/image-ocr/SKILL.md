# Receipt OCR To Excel (filename, date, total_amount)

## Purpose
Convert a directory of receipt images into a single Excel .xlsx artifact by performing bounded OCR per image, extracting only the needed fields (date and total_amount), and writing a verifier-aligned sheet with strict structure and post-write validation.

## When to Use
Use when the task requires batch-processing many images (receipts, invoices, simple forms) into a single table-like artifact with fixed columns and strict formatting (for example, an Excel file with specified sheet name, headers, row ordering, and nulls on extraction failures).

## Procedure
- Step 1: Confirm the output contract and locate inputs (discovery first).
- Determine (from task instructions or environment discovery) the required output path for the .xlsx and the required sheet name and headers.
- Discover input images by scanning the provided workspace/input directory (do not assume hard-coded paths). Collect files with common image extensions (png, jpg, jpeg, webp, tif, tiff).
- Checkpoint: If no images are found, stop and report the discovery results (searched locations and patterns) rather than fabricating output.
- Step 2: Validate tools and prepare bounded OCR configuration.
- In Python, verify imports: PIL (Pillow), pytesseract, and an Excel writer/reader (prefer openpyxl via pandas or openpyxl directly).
- Verify Tesseract availability via pytesseract.get_tesseract_version() when using pytesseract.
- Decide a strict per-image OCR budget:
- Default: 1 OCR pass (baseline).
- Fallback: up to 2 additional variants only if baseline text is empty or extremely low-signal (for example, too few alphanumeric characters).
- Variants should be limited to simple, cheap changes (example: grayscale+autocontrast; one alternate psm). Keep the set fixed for the run.
- Checkpoint: If Tesseract is unavailable, do not loop or retry indefinitely. Record null date/total_amount for all images (or for affected images) and proceed to write the Excel with nulls, plus a brief warning log.
- Step 3: Single-pass batch processing (no dataset-wide reruns).
- For each image (iterate in a deterministic order, e.g., sorted by filename):
- Load the image safely (catch decode errors). If unreadable, record a row with filename and null date/total_amount and continue.
- Run bounded OCR:
- Baseline OCR first.
- Only if baseline is empty/low-signal, try the small fixed fallback variants (up to the budget), then pick the best candidate (for example, the one with the most digits/letters or the highest average confidence when available).
- Parse fields deterministically from the chosen OCR text:
- Extract date using strict patterns first (common numeric dates), then a small set of alternative formats if needed. If multiple candidates exist, choose the most plausible one (for example, earliest in the text near labels like "date").
- Extract total_amount using label-priority rules (prefer lines near "total" over "subtotal", avoid "tax", etc.). Use normalization rules to handle commas and odd spacing in decimals (example: "86. 00" -> "86.00"). Reject obviously invalid amounts (no digits, multiple decimals) and return null if ambiguous.
- Append a row dict with exactly these keys: filename, date, total_amount.
- Hard stop rule: Do not re-run OCR for all images to "improve rules". If parsing quality is insufficient, only adjust parsing logic once, then re-run at most one additional full pass.
- Step 4: Write the Excel artifact once, then validate it from the exact output path.
- Create a tabular structure with exactly 3 columns in this order: filename, date, total_amount.
- Sort rows by filename ascending before writing.
- Write a single-sheet .xlsx with the sheet name exactly "results" to the required output path (create parent directories only if they are within the writable workspace; do not silently redirect the output elsewhere).
- Execution anchor (must do before completion): Reopen the written file from the exact output path and assert:
- File exists and is readable as an .xlsx.
- Exactly one sheet named "results".
- Header row matches exactly and only: filename, date, total_amount (order matters).
- Data rows are sorted by filename (non-decreasing).
- If any assertion fails, fix the writer parameters and rewrite once; if it still fails, stop and report the specific failed assertion and what was found.

## Constraints / Pitfalls
- Never perform unbounded multi-pass OCR or repeated full-dataset reruns. Enforce a strict per-image OCR variant cap and at most one additional full pass for a single parsing logic revision.
- Do not claim completion unless the .xlsx exists at the task-required output path and passes a post-write reload validation (sheet name, exact headers, and filename sort).