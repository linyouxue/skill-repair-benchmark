---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when a task requires OCR-based extraction of structured fields (e.g., dates, monetary totals) from a folder of scanned receipt/document images and writing results to a tabular file (Excel/CSV) with a strict schema. The binding contract specifies:
- The exact input directory and output file path.
- The exact sheet name, column names, column order, row ordering, and formatting of each field.
- Priority-ordered keyword rules for locating the target value and exclusion keywords to skip.
- A null policy when extraction fails.
- Exact evaluator comparison (line-by-line against an oracle), so any extra column/row/sheet or format drift fails.

Before acting, gather:
- The list and count of image files in the input directory (and their extensions).
- The task prompt's keyword priority list, exclusion list, and fallback rule (e.g., "last number on next line").
- The expected formats: ISO date (YYYY-MM-DD), amount as string with exactly two decimals, filename form.
- Which OCR/imaging libraries are pre-installed (do not install new ones unless allowed).

## Possible Failure Modes
- Writing numeric totals as floats instead of strings with exactly two decimals (e.g., `47.7` instead of `"47.70"`), causing line-by-line mismatch.
- Losing leading/trailing formatting: dropping the `.00`, keeping currency symbols (`RM`, `$`), or keeping comma thousand-separators in the stored value (must parse `1,234.56` but store `"1234.56"`).
- Picking up SUBTOTAL, TAX/GST/SST, DISCOUNT, CHANGE, or CASH TENDERED lines because exclusion keywords weren't checked before matching total keywords.
- Ignoring keyword priority: matching generic `TOTAL` before checking for `GRAND TOTAL` or `TOTAL RM`, producing wrong amounts.
- Failing the two-line fallback: when the keyword line has no number, not consulting the next line's *last* number.
- Date parsing pitfalls: ambiguous formats (DD/MM/YY vs MM/DD/YY), 2-digit years, OCR confusions (`O`↔`0`, `l`↔`1`, `S`↔`5`), producing invalid ISO strings instead of null.
- Not setting the field to null on failure — writing empty strings, `NaN`, or `"None"` instead of a real null that pandas writes as an empty cell.
- Row ordering: sorting by numeric value rather than lexicographic filename (or vice versa) when the contract says "ordered by filename".
- Producing extra sheets (pandas default `Sheet1`), extra index column (forgetting `index=False`), or extra columns from debug fields.
- Wrong sheet name capitalization/spacing (must be exactly `results`).
- Iterating non-image files or hidden files in the directory; not filtering by extension.
- Using an OCR config that mangles digits — no preprocessing (thresholding, resize, grayscale) can hurt accuracy on low-quality scans.
- Not handling images that fail OCR at all (exceptions) — should degrade to null, not crash.

## Possible procedures
1. **Enumerate inputs deterministically**: list files in the input directory, filter to image extensions, and sort by filename (string sort) to guarantee stable output order.
2. **OCR each image**:
   - Open with PIL; consider grayscale conversion and mild upscaling for small images.
   - Run `pytesseract.image_to_string`. Split output into lines; keep original casing for debugging but compare uppercased for keyword matching.
3. **Extract total amount** (respect priority):
   - First pass: skip any line containing an exclusion keyword.
   - Search in priority tiers: (a) `GRAND TOTAL`, (b) `TOTAL RM` / `TOTAL: RM`, (c) `TOTAL AMOUNT`, (d) generic `TOTAL`, `AMOUNT`, `TOTAL DUE`, `AMOUNT DUE`, `BALANCE DUE`, `NETT TOTAL`, `NET TOTAL`. Stop at the highest-priority match found.
   - On the matched line, extract the last number matching a pattern like `\d{1,3}(,\d{3})*(\.\d+)?|\d+\.\d+`. If none, look at the next non-empty line and take its last number (fallback rule).
   - Normalize: strip currency symbols, remove commas, cast to float, then format with `f"{value:.2f}"` and store as string.
   - If nothing extracted, store `None`.
4. **Extract date**:
   - Regex candidates for common receipt formats: `DD/MM/YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`, `DD MMM YYYY`, etc. Try multiple patterns.
   - Validate with `datetime.strptime` and reformat to `YYYY-MM-DD`.
   - If parsing fails or ambiguous, store `None`.
5. **Assemble DataFrame** with exactly the required columns in the required order, sorted by filename.
6. **Write Excel** with `openpyxl` engine, `sheet_name="results"`, `index=False`. Do not create any other sheets. Ensure the `total_amount` column dtype is object/string so `"47.70"` is preserved literally.
7. **Recovery on OCR/parse errors**: wrap per-image processing in try/except; on any failure, still append a row with `None` for the failed field(s) rather than skipping the row.

## Verification Checklist
- [ ] Output file exists at the exact required path; only one sheet with the exact required name.
- [ ] Columns are exactly `filename`, `date`, `total_amount` in that order; no index column; no extra columns.
- [ ] Row count equals number of image files in the input directory; rows sorted by filename ascending (string order).
- [ ] `date` values are either valid `YYYY-MM-DD` strings or empty/null (never `NaT`, `"None"`, or malformed).
- [ ] `total_amount` values are strings with exactly two decimals, no currency prefix, no thousand separators (e.g., `"1234.56"`), or empty/null on failure.
- [ ] Exclusion keywords (SUBTOTAL, SUB TOTAL, TAX, GST, SST, DISCOUNT, CHANGE, CASH TENDERED) are never the source of extracted totals.
- [ ] Keyword priority is respected: more specific patterns override generic ones on the same receipt.
- [ ] Two-line fallback is implemented and used when the keyword line lacks a numeric value.
- [ ] Nothing from retrieved examples (unrelated Faker/CSV/histogram code) leaked into the solution.
- [ ] Unrelated files in the workspace are untouched; only the required output file is created/overwritten.
- [ ] Re-open the produced Excel with pandas to confirm sheet name, headers, dtypes (total_amount as string), and row order before finishing.
