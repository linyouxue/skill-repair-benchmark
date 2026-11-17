---
name: xlsx
description: Create, edit, analyze, and recalculate spreadsheets (.xlsx, .xlsm, .csv, .tsv) with formulas, formatting, pandas-based data analysis, visualization, and batch image-to-xlsx extraction pipelines.
license: Proprietary. LICENSE.txt has complete terms
---

# Requirements for Outputs

## All Excel files

### Zero Formula Errors
- Every Excel model MUST be delivered with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)

### Preserve Existing Templates (when updating templates)
- Study and EXACTLY match existing format, style, and conventions when modifying files
- Never impose standardized formatting on files with established patterns
- Existing template conventions ALWAYS override these guidelines

## Financial models

### Color Coding Standards
Unless otherwise stated by the user or existing template

#### Industry-Standard Color Conventions
- **Blue text (RGB: 0,0,255)**: Hardcoded inputs, and numbers users will change for scenarios
- **Black text (RGB: 0,0,0)**: ALL formulas and calculations
- **Green text (RGB: 0,128,0)**: Links pulling from other worksheets within same workbook
- **Red text (RGB: 255,0,0)**: External links to other files
- **Yellow background (RGB: 255,255,0)**: Key assumptions needing attention or cells that need to be updated

### Number Formatting Standards

#### Required Format Rules
- **Years**: Format as text strings (e.g., "2024" not "2,024")
- **Currency**: Use $#,##0 format; ALWAYS specify units in headers ("Revenue ($mm)")
- **Zeros**: Use number formatting to make all zeros "-", including percentages (e.g., "$#,##0;($#,##0);-")
- **Percentages**: Default to 0.0% format (one decimal)
- **Multiples**: Format as 0.0x for valuation multiples (EV/EBITDA, P/E)
- **Negative numbers**: Use parentheses (123) not minus -123

### Formula Construction Rules

#### Assumptions Placement
- Place ALL assumptions (growth rates, margins, multiples, etc.) in separate assumption cells
- Use cell references instead of hardcoded values in formulas
- Example: Use =B5*(1+$B$6) instead of =B5*1.05

#### Formula Error Prevention
- Verify all cell references are correct
- Check for off-by-one errors in ranges
- Ensure consistent formulas across all projection periods
- Test with edge cases (zero values, negative numbers)
- Verify no unintended circular references

#### Documentation Requirements for Hardcodes
- Comment or in cells beside (if end of table). Format: "Source: [System/Document], [Date], [Specific Reference], [URL if applicable]"
- Examples:
  - "Source: Company 10-K, FY2024, Page 45, Revenue Note, [SEC EDGAR URL]"
  - "Source: Company 10-Q, Q2 2025, Exhibit 99.1, [SEC EDGAR URL]"
  - "Source: Bloomberg Terminal, 8/15/2025, AAPL US Equity"
  - "Source: FactSet, 8/20/2025, Consensus Estimates Screen"

# XLSX creation, editing, and analysis

## Overview

A user may ask you to create, edit, or analyze the contents of an .xlsx file. You have different tools and workflows available for different tasks.

## Important Requirements

**LibreOffice Required for Formula Recalculation**: You can assume LibreOffice is installed for recalculating formula values using the `recalc.py` script. The script automatically configures LibreOffice on first run

## Reading and analyzing data

### Data analysis with pandas
For data analysis, visualization, and basic operations, use **pandas** which provides powerful data manipulation capabilities:

```python
import pandas as pd

# Read Excel
df = pd.read_excel('file.xlsx')  # Default: first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # All sheets as dict

# Analyze
df.head()      # Preview data
df.info()      # Column info
df.describe()  # Statistics

# Write Excel
df.to_excel('output.xlsx', index=False)
```

## Excel File Workflows

## CRITICAL: Use Formulas, Not Hardcoded Values

**Always use Excel formulas instead of calculating values in Python and hardcoding them.** This ensures the spreadsheet remains dynamic and updateable.

### ❌ WRONG - Hardcoding Calculated Values
```python
# Bad: Calculating in Python and hardcoding result
total = df['Sales'].sum()
sheet['B10'] = total  # Hardcodes 5000

# Bad: Computing growth rate in Python
growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth  # Hardcodes 0.15

# Bad: Python calculation for average
avg = sum(values) / len(values)
sheet['D20'] = avg  # Hardcodes 42.5
```

### ✅ CORRECT - Using Excel Formulas
```python
# Good: Let Excel calculate the sum
sheet['B10'] = '=SUM(B2:B9)'

# Good: Growth rate as Excel formula
sheet['C5'] = '=(C4-C2)/C2'

# Good: Average using Excel function
sheet['D20'] = '=AVERAGE(D2:D19)'
```

This applies to ALL calculations - totals, percentages, ratios, differences, etc. The spreadsheet should be able to recalculate when source data changes.

## Common Workflow
1. **Choose tool**: pandas for data, openpyxl for formulas/formatting
2. **Create/Load**: Create new workbook or load existing file
3. **Modify**: Add/edit data, formulas, and formatting
4. **Save**: Write to file
5. **Recalculate formulas (MANDATORY IF USING FORMULAS)**: Use the recalc.py script
   ```bash
   python recalc.py output.xlsx
   ```
6. **Verify and fix any errors**:
   - The script returns JSON with error details
   - If `status` is `errors_found`, check `error_summary` for specific error types and locations
   - Fix the identified errors and recalculate again
   - Common errors to fix:
     - `#REF!`: Invalid cell references
     - `#DIV/0!`: Division by zero
     - `#VALUE!`: Wrong data type in formula
     - `#NAME?`: Unrecognized formula name

### Creating new Excel files

```python
# Using openpyxl for formulas and formatting
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# Add data
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

# Add formula
sheet['B2'] = '=SUM(A1:A10)'

# Formatting
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# Column width
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

### Editing existing Excel files

```python
# Using openpyxl to preserve formulas and formatting
from openpyxl import load_workbook

# Load existing file
wb = load_workbook('existing.xlsx')
sheet = wb.active  # or wb['SheetName'] for specific sheet

# Working with multiple sheets
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    print(f"Sheet: {sheet_name}")

# Modify cells
sheet['A1'] = 'New Value'
sheet.insert_rows(2)  # Insert row at position 2
sheet.delete_cols(3)  # Delete column 3

# Add new sheet
new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

## Recalculating formulas

Excel files created or modified by openpyxl contain formulas as strings but not calculated values. Use the provided `recalc.py` script to recalculate formulas:

```bash
python recalc.py <excel_file> [timeout_seconds]
```

Example:
```bash
python recalc.py output.xlsx 30
```

The script:
- Automatically sets up LibreOffice macro on first run
- Recalculates all formulas in all sheets
- Scans ALL cells for Excel errors (#REF!, #DIV/0!, etc.)
- Returns JSON with detailed error locations and counts
- Works on both Linux and macOS

## Batch image-to-xlsx pipelines

When the deliverable is a per-row xlsx whose cells are fields extracted
from a directory of images (scans of receipts, invoices, forms, or tabular
documents), the workflow differs from editing an existing workbook. The
agent is simultaneously running OCR, parsing OCR text into named fields,
and writing a structured workbook under an iteration budget. Three ordered
rules prevent the common failure where correct fixes land mid-run but
never reach the shipped artifact.

1. **Cache multi-variant OCR once, up front.** Enumerate every input
   image, run multi-pass OCR (see image-ocr skill's Multi-Pass OCR
   Strategy), and persist per-variant text to disk keyed by filename.
   Subsequent iteration edits the extractor and reads from this cache,
   never re-running Tesseract.
2. **Iterate the extractor in memory; re-run the full corpus on every
   edit.** Each extractor change must be followed by a full-corpus pass
   that recomputes every row before any xlsx is overwritten. Per-image
   debug iterations that fix one record in isolation routinely regress
   others.
3. **Overwrite the xlsx atomically at the end of each full-corpus pass.**
   The on-disk deliverable is replaced in one write after a successful
   full pass, so budget exhaustion at any later point leaves the best
   complete artifact in place. Missing field values are written as `None`
   (openpyxl → empty cell), never as empty string.

```python
import json
from pathlib import Path
from openpyxl import Workbook

def build_ocr_cache(input_dir, cache_path, ocr_variants_fn, extensions):
    """Run multi-pass OCR on every input file; persist per-variant text."""
    cache = {}
    for p in sorted(Path(input_dir).iterdir()):
        if p.suffix.lower() in extensions:
            cache[p.name] = ocr_variants_fn(str(p))
    with open(cache_path, "w") as f:
        json.dump(cache, f)
    return cache

def write_rows_atomic(rows, out_path, sheet_name, headers):
    """Overwrite xlsx in one shot. None stays None (empty cell), never ''."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    for row in rows:
        ws.append([v if v is not None else None for v in row])
    wb.save(out_path)

def run_full_corpus(cache, extract_fn):
    """Recompute every row from the frozen OCR cache."""
    return [extract_fn(name, variants) for name, variants in sorted(cache.items())]
```

Decision rule: if the task supplies input images and expects a per-image
row in an xlsx deliverable, follow the cache → iterate-in-memory →
atomic-write pattern. If the task supplies already-structured input (a
CSV, an existing xlsx, a JSON array), use the standard openpyxl workflow
above.

Verification: after each `write_rows_atomic` call, re-open the file and
assert row count equals the input directory's eligible file count, that
header matches the deliverable schema, and that no cell contains the
empty string `""` where a missing value was intended. If any check fails,
do not advance to further extractor edits — fix the writer first,
otherwise subsequent passes will not surface the regression.


## Best Practices

### Library Selection
- **pandas**: Best for data analysis, bulk operations, and simple data export
- **openpyxl**: Best for complex formatting, formulas, and Excel-specific features

### Working with openpyxl
- Cell indices are 1-based (row=1, column=1 refers to cell A1)
- Use `data_only=True` to read calculated values: `load_workbook('file.xlsx', data_only=True)`
- **Warning**: If opened with `data_only=True` and saved, formulas are replaced with values and permanently lost
- For large files: Use `read_only=True` for reading or `write_only=True` for writing
- Formulas are preserved but not evaluated - use recalc.py to update values

### Working with pandas
- Specify data types to avoid inference issues: `pd.read_excel('file.xlsx', dtype={'id': str})`
- For large files, read specific columns: `pd.read_excel('file.xlsx', usecols=['A', 'C', 'E'])`
- Handle dates properly: `pd.read_excel('file.xlsx', parse_dates=['date_column'])`

## Code Style Guidelines
**IMPORTANT**: When generating Python code for Excel operations:
- Write minimal, concise Python code without unnecessary comments
- Avoid verbose variable names and redundant operations
- Avoid unnecessary print statements

**For Excel files themselves**:
- Add comments to cells with complex formulas or important assumptions
- Document data sources for hardcoded values
- Include notes for key calculations and model sections

## Common Pitfalls

- **Hardcoding calculated values** instead of writing Excel formulas. See the CRITICAL section above.
- **Skipping formula recalculation** after openpyxl writes. openpyxl stores formula strings but not evaluated results; always run `recalc.py` and inspect its JSON error summary before shipping.
- **Emitting empty string `""` instead of `None` for missing cells** when building per-row xlsx from extractors. Exact-match verifiers treat `""` as a wrong present value, not as a null-matching blank. Assign `None` in openpyxl — never substitute `""` for a missing extraction.
- **Shipping intermediate-state artifacts under an iteration budget.** Writing xlsx after each per-record extractor edit (rather than after a full-corpus pass) ships whatever state existed when budget ran out — often predating correct fixes discovered mid-run. The combined remedy: build a frozen OCR cache so per-record edits are cheap in-memory, re-run the full corpus on every edit, and overwrite the deliverable atomically only after the full-corpus pass. See "Batch image-to-xlsx pipelines".
