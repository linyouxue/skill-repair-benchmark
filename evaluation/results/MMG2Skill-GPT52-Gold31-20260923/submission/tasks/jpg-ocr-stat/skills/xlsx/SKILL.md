---
name: xlsx
description: Comprehensive spreadsheet creation, editing, and analysis with support
  for formulas, formatting, data analysis, and visualization.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. Prepare the final table in memory **without re-running expensive upstream work** (e.g., use cached OCR/parsing results): rows must be `filename, date, total_amount` and sorted by `filename`.
2. Create the workbook with **exactly one sheet** named `results`:
   - With openpyxl: `wb = Workbook(); ws = wb.active; ws.title = "results"` and **remove any extra default sheets** if created.
   - Or with pandas: `df.to_excel(path, sheet_name="results", index=False, engine="openpyxl")` (ensure only one sheet is written).
3. Write the header row exactly as: `filename`, `date`, `total_amount` (no extra columns).
4. Append each row in filename order; represent extraction failures as `None` (so Excel cell is blank), and keep `total_amount` as a **string with exactly two decimals** when present.
5. Save the file to the required path (e.g., `/app/workspace/stat_ocr.xlsx`) and **explicitly verify on disk**:
   - Re-open the workbook (`load_workbook`) and check: `wb.sheetnames == ["results"]`.
   - Read the first row to confirm the header matches exactly.
   - Confirm row count equals `number_of_images + 1` and that filenames are sorted.
## Expected Result
An `.xlsx` file saved at the target path containing **one** sheet named `results` with **only** the three required columns, correctly ordered rows, correct null handling, and verified structure/content after saving.
