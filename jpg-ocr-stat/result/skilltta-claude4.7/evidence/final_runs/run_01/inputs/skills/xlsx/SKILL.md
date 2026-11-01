---
name: xlsx
description: "Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization, including strict-schema tabular outputs with null-preserving semantics for OCR/extraction pipelines."
license: Proprietary. LICENSE.txt has complete terms
---

# Requirements for Outputs

## All Excel files

### Zero Formula Errors
- Every Excel model MUST be delivered with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?).

### Preserve Existing Templates (when updating templates)
- Study and EXACTLY match existing format, style, and conventions when modifying files.
- Never impose standardized formatting on files with established patterns.
- Existing template conventions ALWAYS override these guidelines.

## Financial models

### Color Coding Standards
Unless otherwise stated by the user or existing template:

- **Blue text (RGB: 0,0,255)**: Hardcoded inputs and numbers users will change for scenarios.
- **Black text (RGB: 0,0,0)**: ALL formulas and calculations.
- **Green text (RGB: 0,128,0)**: Links pulling from other worksheets within same workbook.
- **Red text (RGB: 255,0,0)**: External links to other files.
- **Yellow background (RGB: 255,255,0)**: Key assumptions needing attention or cells that need updating.

### Number Formatting Standards
- **Years**: Format as text strings (e.g., "2024" not "2,024").
- **Currency**: Use $#,##0 format; ALWAYS specify units in headers ("Revenue ($mm)").
- **Zeros**: Use number formatting to make all zeros "-", including percentages (e.g., "$#,##0;($#,##0);-").
- **Percentages**: Default to 0.0% format (one decimal).
- **Multiples**: Format as 0.0x for valuation multiples.
- **Negative numbers**: Use parentheses (123) not minus -123.

### Formula Construction Rules
- Place ALL assumptions in separate assumption cells; reference them in formulas.
- Use cell references instead of hardcoded values (e.g., `=B5*(1+$B$6)`).
- Verify ranges, references, and consistency across projection periods.
- Document hardcodes with source information in a cell comment or adjacent cell.

# XLSX creation, editing, and analysis

## Overview

Use pandas for data analysis and simple reads/writes; use openpyxl for formulas, formatting, and strict null/string preservation.

## Important Requirements

**LibreOffice Required for Formula Recalculation**: Assume LibreOffice is installed; recalc formulas with the provided `recalc.py` script.

## Reading and analyzing data

```python
import pandas as pd

df = pd.read_excel('file.xlsx')               # first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # all sheets
```

## CRITICAL: Use Formulas, Not Hardcoded Values

For financial models and templates, always use Excel formulas instead of pre-computing values in Python and writing numeric constants. For pure data-dump outputs (no formulas required by the task), prefer the writing patterns below.

## Common Workflow

1. Choose the right tool: pandas for data, openpyxl for formulas/formatting/strict schemas.
2. Create or load the workbook.
3. Modify data, formulas, and formatting.
4. Save.
5. If formulas were used, run `python recalc.py <file>` and fix any errors reported.

## Creating new Excel files (formulas + formatting)

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])
sheet['B2'] = '=SUM(A1:A10)'
sheet['A1'].font = Font(bold=True, color='FF0000')
wb.save('output.xlsx')
```

## Editing existing Excel files

```python
from openpyxl import load_workbook
wb = load_workbook('existing.xlsx')
sheet = wb.active
sheet['A1'] = 'New Value'
wb.save('modified.xlsx')
```

## Recalculating formulas

```bash
python recalc.py output.xlsx 30
```

Inspect the returned JSON; fix any reported `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?` and recalc again.

# Exact-match tabular outputs (data dumps, OCR/extraction pipelines)

Many tasks require a strict schema (exact sheet name, exact column names and order, exact row order, strict null semantics, exact string formatting). Formula and color-coding guidance above does not apply to these outputs.

## Null vs empty-string vs NaN

- Verifiers that compare cells line-by-line typically treat `None`, `''`, and `'None'` as different values.
- Pandas object columns containing `None` can serialize as empty strings in some writer configurations; using openpyxl directly guarantees true empty cells.
- To preserve `None` with pandas: `df = df.astype(object).where(pd.notna(df), None)` before `to_excel`.

## String-typed numeric columns (fixed decimals)

When a column must preserve exact string form such as `'47.70'` (not float `47.7`):

- Build values as Python `str` using `f'{v:.2f}'` BEFORE constructing the DataFrame or writing cells.
- Keep the column dtype `object`.
- Set the Excel cell `number_format = '@'` (text) to prevent Excel/LibreOffice from re-formatting the number and dropping trailing zeros.
- Verify by reopening the workbook and asserting the cell value is a `str` matching the expected pattern.

## Recommended pattern (openpyxl, null-preserving)

```python
from openpyxl import Workbook, load_workbook

def write_strict_table(rows, columns, out_path, sheet_name='results', text_columns=()):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(list(columns))
    text_col_idx = {columns.index(c) + 1 for c in text_columns if c in columns}
    for row in rows:
        values = [row.get(c, None) for c in columns]
        # Normalize: None stays None; strings stay strings; never '' or 'None' or NaN text
        ws.append(values)
        for ci in text_col_idx:
            ws.cell(row=ws.max_row, column=ci).number_format = '@'
    wb.save(out_path)

def verify_strict_table(path, columns, sheet_name='results'):
    wb = load_workbook(path)
    assert wb.sheetnames == [sheet_name], wb.sheetnames
    ws = wb[sheet_name]
    header = [c.value for c in ws[1]]
    assert header == list(columns), header
```

## Checklist for exact-match outputs

- [ ] Exactly one sheet, named exactly as the task requires.
- [ ] Column names and order exactly match the task spec.
- [ ] Rows sorted as required (typically lexicographic by a key column).
- [ ] No extra columns, no index column, no trailing blank rows, no extra sheets.
- [ ] Missing values are Python `None` → empty Excel cells (not `''`, not `'None'`, not `NaN`).
- [ ] String-typed numeric columns are stored as `str` with the required decimal count and `number_format='@'`.
- [ ] Dates (if string) are stored as `str` in the required format (e.g., `'YYYY-MM-DD'`), not Excel date serials.
- [ ] Re-open the file post-write and assert cell types and values match the expected contract.

## Best Practices

### Library Selection
- **pandas**: data analysis, bulk operations, simple exports.
- **openpyxl**: complex formatting, formulas, strict null/string preservation, exact-match outputs.

### Working with openpyxl
- Cell indices are 1-based.
- Use `data_only=True` to read calculated values; do not re-save such a workbook or you will lose formulas.
- For large files, use `read_only=True` / `write_only=True`.

### Working with pandas
- Specify dtypes to avoid inference issues: `pd.read_excel('f.xlsx', dtype={'id': str})`.
- For large files, read specific columns and parse dates explicitly.

## Code Style Guidelines

**IMPORTANT**: When generating Python code for Excel operations:
- Write minimal, concise code without unnecessary comments.
- Avoid verbose variable names and redundant operations.
- Avoid unnecessary print statements.

**For Excel files themselves**:
- Add comments only to cells with complex formulas or important assumptions.
- Document data sources for hardcoded values.
- Include notes for key calculations in financial models (not in pure data dumps).
