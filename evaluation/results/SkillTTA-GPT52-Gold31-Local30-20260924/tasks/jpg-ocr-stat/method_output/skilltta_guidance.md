# SKILL.md

## When to use
Use this skill when you must batch-process a directory of receipt-like scanned images, extract specific structured fields via OCR (notably a date and a total amount), and write **exactly** a single Excel sheet with a fixed schema. Before acting, gather:
- The exact input directory path and which image extensions appear (e.g., `.jpg`, `.png`).
- Output requirements: output file path, **single sheet name**, exact column names/order, ordering rule for rows, null-handling rules, and strict “no extra sheets/rows/columns” constraints.
- Domain cues for locating the “total amount” (priority keyword list + exclusion keywords + cross-line fallback) and formatting constraints (ISO date; 2-decimal monetary string).

## Possible Failure Modes
- **Excel format drift**: extra sheet(s), wrong sheet name, extra index column, blank row at end, wrong header capitalization, or columns out of order—causes line-by-line comparison failure.
- **Row ordering mistakes**: sorting lexicographically vs numerically (e.g., `10.jpg` before `2.jpg`) or not sorting at all; mixing full paths instead of basenames in `filename`.
- **OCR text quality issues**: failing to preprocess images (orientation, contrast) leading to missed digits; not using appropriate Tesseract configuration (PSM/OEM) for receipts.
- **Total amount mis-detection**:
  - Picking up subtotals/tax/discount/change due to ignoring exclusion keywords.
  - Matching a non-total number on the same line (e.g., phone number, invoice id).
  - Not handling cases where keyword and amount appear on different lines.
  - Not supporting comma-separated numbers or currency tokens and producing malformed values.
- **Date parsing errors**: extracting multiple candidate dates and choosing the wrong one; not normalizing to `YYYY-MM-DD`; locale ambiguity (DD/MM vs MM/DD); returning invalid dates instead of null.
- **Formatting errors**: total amount not represented as a string with **exactly two decimals**; writing numeric type to Excel that later renders differently; leaving currency symbols.
- **Null handling inconsistencies**: using empty string/`"null"` instead of actual null; populating one field when the task requires null only for that field (or vice versa).
- **Partial file coverage**: skipping images due to extension assumptions or hidden files; processing non-image files accidentally and crashing.
- **Non-determinism / fragile heuristics**: relying on “largest number” or “last number in document” without keyword logic; not guarding against OCR artifacts.

## Possible procedures
1. **Inventory & stable ordering**
   - List all files under the input directory; filter to image-like extensions.
   - Use basenames for `filename`.
   - Sort deterministically; if filenames are numeric-like, prefer a “natural sort” (split digits) to match human ordering.

2. **OCR extraction pipeline**
   - Load each image with PIL.
   - Preprocess for OCR robustness: grayscale, resize (e.g., scale up), denoise/light thresholding, and optional rotation correction if needed.
   - Run Tesseract via `pytesseract.image_to_string` (optionally with a tuned `--psm` suitable for blocks/lines).
   - Keep both the raw text and a normalized version (e.g., uppercased, whitespace-collapsed) for keyword matching while preserving original lines for numeric extraction.

3. **Parse total amount with keyword priority + exclusions**
   - Split OCR output into lines; iterate lines in document order.
   - For each line, skip immediately if it contains any exclusion keyword (case-insensitive, normalized).
   - Search for inclusion keywords in **priority order**; when a keyword hits:
     - Try to extract a monetary number from the same line using a conservative regex that supports commas and decimals.
     - If no number is found (keyword-only line), apply the documented fallback: inspect the **next non-empty line** and take the **last** number on that line.
   - Normalize the extracted number:
     - Remove commas and currency tokens.
     - Convert to a decimal-like representation and then format as a string with exactly two decimal places.
   - If multiple candidates exist, pick the first match according to keyword priority and scan order (avoid “best guess” that changes across runs).

4. **Parse date and normalize to ISO**
   - Extract date candidates using regex patterns covering common receipt formats (with separators like `-`, `/`, `.`, and month names if present).
   - Parse with strict validation (use a date parser library if available; otherwise implement controlled parsing).
   - Resolve ambiguities deterministically (e.g., prefer formats typical for receipts in your dataset, or pick the candidate closest to “DATE” label if you implement label proximity).
   - Output `YYYY-MM-DD`; if parsing fails, set to null.

5. **Null policy**
   - Treat `date` and `total_amount` independently: if one fails, only that field becomes null.
   - Ensure you emit actual null values in the dataframe (e.g., `None`/`NaN`) so the Excel writer produces empty cells.

6. **Write Excel with strict schema**
   - Build a dataframe with exactly three columns: `filename`, `date`, `total_amount` in that order.
   - Ensure the first row is the header and there are no extra rows.
   - Write to the required path with a single sheet named exactly as specified; disable index writing.
   - Avoid adding formatting, additional worksheets, or metadata that could create extra visible content.

7. **Recovery / debugging loop**
   - If many totals/dates become null, inspect OCR output for a few samples and adjust preprocessing or keyword matching (e.g., handle OCR confusions like `T0TAL` vs `TOTAL` with cautious normalization).
   - Add lightweight logging during development, but ensure it does not alter the output artifact.

## Verification Checklist
- [ ] All image files in the input directory were considered; non-images do not crash the run.
- [ ] Output file exists at the required path and is a valid `.xlsx`.
- [ ] Workbook contains **exactly one** sheet with the exact required name.
- [ ] Sheet has **exactly three** columns with exact headers and order: `filename`, `date`, `total_amount`.
- [ ] No extra index column; no extra blank rows; no extra sheets.
- [ ] Rows are ordered by filename according to the required interpretation (confirm by reading back the Excel and checking order).
- [ ] `filename` values are basenames (not full paths) and match the source files.
- [ ] `date` values are either null or strictly `YYYY-MM-DD` and represent valid calendar dates.
- [ ] `total_amount` values are either null or strings with exactly two decimal places; no currency symbols; commas removed; consistent formatting.
- [ ] Exclusion keywords prevent selecting tax/subtotal/discount/change-like amounts; cross-line keyword/amount cases are handled.
- [ ] Read back the generated Excel (via pandas/openpyxl) and compare schema + a few rows to ensure deterministic, evaluator-visible correctness.
- [ ] Retrieved examples were used only for general tactics (I/O hygiene, error handling), not copied as task-specific facts or outputs.
