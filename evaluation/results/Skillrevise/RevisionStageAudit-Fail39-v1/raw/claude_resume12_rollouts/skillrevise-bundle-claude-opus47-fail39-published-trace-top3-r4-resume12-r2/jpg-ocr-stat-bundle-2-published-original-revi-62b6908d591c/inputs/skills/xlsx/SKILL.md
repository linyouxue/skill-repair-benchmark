# xlsx

## Purpose
Reusable workflow for creating, editing, and verifying `.xlsx` / `.xlsm` / `.csv` outputs with Python. Covers two branches: (A) plain tabular data-dump workbooks and (B) formula-bearing spreadsheets that need recalculation and formatting.

## When to Use
Use when the task requires producing or modifying a spreadsheet file whose structure, formulas, formatting, or workbook layout is part of the deliverable. Do NOT use as general guidance for upstream work (e.g., OCR, scraping, modeling) whose only connection to a spreadsheet is a final write step; in those cases, apply only Branch A below and ignore the formula/recalc material.

## Procedure
- Classify the branch before writing any code:
- Branch A (data dump): task only needs rows/columns written to a specified file. No formulas required.
- Branch B (model): task requires formulas, cross-sheet links, formatting, or recalculated values. Record the branch; it determines which later steps apply.
- Discover the environment and contract:
- Read the exact output path, sheet name (if specified), column order, and row semantics from the task text. Do not invent paths or schemas.
- Confirm Python libraries available (`openpyxl`, `pandas`). If a recalculation helper is needed in Branch B, locate it by discovery (e.g., search the workspace) rather than assuming a filename.
- Build the workbook:
- Branch A: use `openpyxl.Workbook()` or `pandas.DataFrame.to_excel(..., index=False)`. Write a header row only if the task implies one. Preserve the exact column order required. Use `None`/empty cell for fields that could not be determined; never fabricate values.
- Branch B: write formulas as strings prefixed with `=`; keep hardcoded inputs separate from calculated cells; use cell references rather than inline literals; match any pre-existing template's formatting and conventions exactly when editing an existing file.
- Recalculate (Branch B only): invoke the available recalculation tool on the saved file, then parse its output for formula errors (`#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#N/A`). Fix and repeat until zero errors. Skip this step entirely in Branch A.
- Verify against the observable contract:
- Reload the saved file with `openpyxl.load_workbook(path)` (use `data_only=True` only for reading, never for the saved artifact).
- Assert: file exists at the task-specified path, target sheet is present, column headers (if required) match, and row count equals the expected number of records.
- Report mismatches explicitly instead of silently rewriting the file to a different location.

## Constraints / Pitfalls
- Do not emit financial-model conventions (color coding, number formats, assumption placement) unless the task or an existing template requires them.
- Do not run the formula-recalculation step when no formulas were authored; it adds no value and may mask environment issues.
- Never silently redirect the output to a different path if writing fails; inspect permissions and mounts, then write to the exact requested path.
- Avoid hardcoding calculated values in Branch B; use Excel formulas so the workbook stays dynamic.
- When editing an existing file, load with `openpyxl.load_workbook` (not pandas round-trip) to preserve formulas and styles.
- Keep code minimal; avoid print noise and speculative formatting that is not part of the contract.