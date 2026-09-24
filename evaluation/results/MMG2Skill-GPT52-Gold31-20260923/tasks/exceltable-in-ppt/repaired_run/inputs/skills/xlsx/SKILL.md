---
name: xlsx
description: Spreadsheet (.xlsx) reading and editing with preservation of formulas
  and formatting, avoiding accidental conversion of formulas to hardcoded values.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. Load the workbook for editing with `openpyxl.load_workbook(path)` (do **not** use `data_only=True` when you intend to preserve formulas).
2. Inspect the sheet to identify which cells are formulas vs hardcoded inputs (e.g., `cell.value` starts with `=` / `cell.data_type == "f"`), especially around the target currency pair.
3. Update only the intended **non-formula** cell(s); leave any formula cell values untouched so formulas remain formulas.
4. Save the workbook and re-open it to confirm:
   - updated input cell has the new numeric value, and
   - representative dependent cells still contain formula strings (start with `=`), not computed hardcoded numbers.
5. Recalculate with `python recalc.py file.xlsx` only when you need refreshed cached results; do not replace formulas with computed values in Python.
## Expected Result
The workbook reflects the updated input(s) while all original formula cells remain formulas and formatting is preserved.
