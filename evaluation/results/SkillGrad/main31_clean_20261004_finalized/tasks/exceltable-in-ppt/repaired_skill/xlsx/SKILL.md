---
name: xlsx
description: "Create, edit, and analyze spreadsheet files (XLSX/XLSM/CSV/TSV) while preserving formulas, formatting, and recalculation, including when spreadsheets are embedded inside other Office documents."
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

df = pd.read_excel('file.xlsx')
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)

summary = df.describe(include='all')
summary.to_excel('summary.xlsx')
```

## Excel File Workflows

## CRITICAL: Use Formulas, Not Hardcoded Values

**Always use Excel formulas instead of calculating values in Python and hardcoding them.** This ensures the spreadsheet remains dynamic and updateable.

```python
# openpyxl: write formulas as strings so Excel/LibreOffice can recalc
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws['A1'] = 1
ws['A2'] = 2
ws['A3'] = '=SUM(A1:A2)'
wb.save('out.xlsx')
```

## Workflow (skim before operating)

### Plan the artifact you must change (file bytes vs rendered preview)
1. Identify what the evaluator can “see”: raw workbook bytes, a rendered preview inside another container (PPTX/DOCX), or both.
2. For embedded spreadsheets in Office containers, treat success as container-level unless proven otherwise: plan to update (a) the embedded workbook bytes and (b) any display cache the host app renders on-canvas.
3. Before edits, trace host XML → relationship file(s) to enumerate *all* parts that contribute to what is visible (e.g., slide XML → slide rels → `ppt/media/*`), and record a quick hash of each referenced preview part.
4. After edits, re-hash the same preview parts; if any remain unchanged, fail fast and regenerate/replace the preview (or route through an Office-engine open+save that re-renders) before finalizing.

## Operation: Modify an embedded workbook inside an Office container
Update the embedded workbook bytes (e.g., PPTX/DOCX zip member) without breaking formulas or formatting.

```python
from zipfile import ZipFile
from io import BytesIO
from openpyxl import load_workbook

with ZipFile(container_path) as z:
    xlsx_bytes = z.read(embedded_member)
wb = load_workbook(BytesIO(xlsx_bytes), data_only=False)
ws = wb.active
ws[cell_addr] = new_value
buf = BytesIO(); wb.save(buf)
updated_xlsx = buf.getvalue()
```

Read references/pptx_ole_preview.md when the spreadsheet is embedded in a PPTX and success depends on what appears on the slide canvas.
Skip when you are delivering a standalone .xlsx (no container) or success is explicitly judged only by embedded workbook bytes.

## Recalculating formulas

Excel files created or modified by openpyxl contain formulas as strings but not calculated values. Use the provided `recalc.py` script to recalculate formulas:

```bash
python recalc.py <excel_file> [timeout_seconds]
```

## Common Pitfalls
- Saving a workbook loaded with `data_only=True` will destroy formulas by replacing them with cached values.
- For Office containers (PPTX/DOCX), verifying only the embedded workbook can miss a stale rendered preview/cache that is actually evaluated.
- Passing Python-calculated numbers where a formula should exist makes models non-updatable and hard to audit.
