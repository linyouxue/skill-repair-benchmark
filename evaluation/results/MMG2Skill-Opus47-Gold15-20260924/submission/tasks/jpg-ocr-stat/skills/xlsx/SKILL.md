---
name: xlsx
description: Comprehensive spreadsheet creation, editing, and analysis with support
  for formulas, formatting, data analysis, and visualization.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. Choose tool: `pandas` for tabular data export/analysis, `openpyxl` for formulas/formatting/multi-sheet editing.
2. Create or load the workbook; write data and, where applicable, Excel formulas rather than Python-computed constants.
3. For tasks like this one (strict schema, one sheet, exact columns), use pandas: build a DataFrame sorted by filename with columns `filename,date,total_amount` and call `df.to_excel(path, sheet_name='results', index=False)`.
4. Ensure `total_amount` values are strings with exactly two decimals (e.g., `f"{value:.2f}"`); missing values are Python `None` so pandas writes empty cells.
5. If formulas were used, run `python recalc.py <file>` and fix any reported errors.
6. Re-open the saved file (e.g., `pd.read_excel(path)`) to verify sheet name, column order, row order, and cell contents match the spec before finishing.
## Expected Result
A valid xlsx with exactly the required sheet, columns, and rows, whose contents match what the extraction script last produced.
