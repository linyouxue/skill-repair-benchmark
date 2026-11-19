---
name: xlsx
description: "Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization. When Claude needs to work with spreadsheets (.xlsx, .xlsm, .csv, .tsv, etc) for: (1) Creating new spreadsheets with formulas and formatting, (2) Reading or analyzing data, (3) Modify existing spreadsheets while preserving formulas, (4) Data analysis and visualization in spreadsheets, or (5) Recalculating formulas"
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

**Formula recalculation (preferred) + error scanning**: Use `skills/xlsx/recalc.py` to *attempt* a recalculation and then scan for Excel error values.

- If LibreOffice Calc is available (`soffice` / `libreoffice`), the script will round-trip the file in headless mode to refresh cached formula results.
- If LibreOffice is not available in the environment, the script will still scan the workbook and report that recalculation was skipped.

This means you can always run the script as a post-save sanity check, but you should not assume formula values were updated unless `recalc.attempted=true` and `recalc.success=true`.

### Safe `openpyxl` import (vendored)
Some SkillHone runtimes do not have `openpyxl` preinstalled. This Skill vendors `openpyxl` wheels under `skills/xlsx/vendor/`.

Simplest pattern for ad-hoc scripts (run from the repo root so `skills/` is on `sys.path`):

```python
import skills.xlsx.recalc  # bootstraps vendored wheels if needed
from openpyxl import load_workbook, Workbook
```

If you are not running from the repo root, ensure the repo is on `sys.path` (or set `PYTHONPATH=.`), or see the “Vendored dependencies (openpyxl)” section below for manual wheel bootstrapping.

**Common failure mode**: `ModuleNotFoundError: No module named 'openpyxl'` in minimal runtimes. Fix by importing `skills.xlsx.recalc` *before* importing `openpyxl` (it prepends the vendored wheels).

Example (for scripts saved inside the repo):

```python
import sys
from pathlib import Path

# Ensure repo root is importable even if you run this script elsewhere
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

import skills.xlsx.recalc  # bootstraps vendored openpyxl wheels
from openpyxl import load_workbook
```

Example (for one-off snippets): run from the repo root so `skills/` is importable:

```bash
cd <repo-root>
PYTHONPATH=. python3 - <<'PY'
import skills.xlsx.recalc
from openpyxl import load_workbook
print("openpyxl ok")
PY
```

## Reading and analyzing data

### Tip: Prefer API downloads over UI scraping when possible
If a source provides a stable API/CSV endpoint, prefer that over browser automation. It is usually faster, more reproducible, and easier to debug.

Common examples in macro/data-workbooks:
- **IMF DataMapper API**: JSON endpoints like `https://www.imf.org/external/datamapper/api/v1/<INDICATOR>/<COUNTRY>`
  - Some indicators may not be available (you might get a response containing only `countries/groups/regions` and no `values`). Treat that as “indicator unsupported” and choose a different series.
- **ECB SDMX API**: CSV endpoints like `https://data-api.ecb.europa.eu/service/data/<FLOWREF>?startPeriod=...` (set `Accept: text/csv`)
  - If you get HTTP 406, adjust the `Accept` header (many endpoints accept plain `text/csv`).
- **Dataverse API**: direct file downloads like `https://dataverse.nl/api/access/datafile/<ID>`
  - Useful when a page embeds “datafile” IDs but hides direct links.

When using APIs:
- Always parse the response and then write values into the workbook.
- Keep *all calculations* (growth extensions, projections, ratios) as **Excel formulas**, not Python.

### Data analysis: prefer openpyxl-only (assume pandas is unavailable)
Many SkillHone runtimes do **not** include `pandas` (importing it may crash your run). Prefer **openpyxl** for reading/writing and do calculations with **Excel formulas**, not Python.

If `pandas` is available, you may use it *only after confirming it imports* (wrap the import in `try/except`), but never depend on it for required steps.

### Tip: Large JSON responses
Some public APIs return large JSON payloads. Prefer fetching a single country/series when possible (e.g., DataMapper `/.../<INDICATOR>/<COUNTRY>` rather than downloading all countries).

#### Optional imports: never combine with required imports
Do **not** write `import openpyxl, pandas as pd` (or similar). In Python, that entire statement fails if the optional dependency is missing.

Instead, import required libraries first, then guard optional ones:

```python
import skills.xlsx.recalc  # optional: bootstraps vendored openpyxl wheels
from openpyxl import load_workbook

try:
    import pandas as pd
except ModuleNotFoundError:
    pd = None
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
1. **Choose tool**: openpyxl for structured edits (formulas/formatting)
2. **Create/Load**: Create new workbook or load existing file
3. **Modify**: Add/edit data, formulas, and formatting (keep templates intact)
4. **Save**: Write to file
5. **Scan for formula errors**: Use the bundled script
   ```bash
   python3 skills/xlsx/recalc.py output.xlsx
   ```
   - If LibreOffice is installed, cached formula results may be refreshed.
   - If not, the script still scans and reports Excel error values.
6. **Verify and fix any errors**:
   - If `status` is `errors_found`, check `error_summary` for locations
   - Fix references/types/divisions and re-run the scan

### Data ingestion workflow (macro / economic datasets)
A common pattern is: **download raw data → paste values into input columns → write formulas for everything else**.

- Keep downloaded series as raw values (with a source note in an adjacent cell if needed).
- Use formulas for:
  - growth extensions / projections
  - depreciation rates, averages
  - ratios (e.g., K/Y)
  - log transforms (LnK, LnY)
  - TREND extensions

Avoid doing these calculations in Python; let Excel remain the source of truth.

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
python3 skills/xlsx/recalc.py <excel_file> [timeout_seconds]
```

Example:
```bash
python3 skills/xlsx/recalc.py output.xlsx 30
```

The script:
- **If LibreOffice is available**: round-trips the workbook in headless mode to refresh cached formula results
- **Always**: scans for cached Excel error values (#REF!, #DIV/0!, etc.) and counts formulas
- **Additionally**: emits a lightweight `numeric_stats` block (min/max/mean_abs over numeric cells) to help catch unit/scale mistakes
- Returns JSON with detailed error locations and counts (and a `recalc` diagnostic block)
- Works in constrained environments by importing vendored `openpyxl` wheels if needed

## Formula Verification Checklist

Quick checks to ensure formulas work correctly:

### Essential Verification
- [ ] **Test 2-3 sample references**: Verify they pull correct values before building full model
- [ ] **Column mapping**: Confirm Excel columns match (e.g., column 64 = BL, not BK)
- [ ] **Row offset**: Remember Excel rows are 1-indexed (DataFrame row 5 = Excel row 6)

### Common Pitfalls
- [ ] **Missing values**: Check for blanks/None in required input ranges before building dependent formulas
- [ ] **Far-right columns**: FY data often in columns 50+
- [ ] **Multiple matches**: Search all occurrences, not just first
- [ ] **Division by zero**: Check denominators before using `/` in formulas (#DIV/0!)
- [ ] **Wrong references**: Verify all cell references point to intended cells (#REF!)
- [ ] **Cross-sheet references**: Use correct format (Sheet1!A1) for linking sheets

### Formula Testing Strategy
- [ ] **Start small**: Test formulas on 2-3 cells before applying broadly
- [ ] **Verify dependencies**: Check all cells referenced in formulas exist
- [ ] **Test edge cases**: Include zero, negative, and very large values

### Interpreting recalc.py Output
The script returns JSON with error details:
```json
{
  "status": "success",           // or "errors_found"
  "total_errors": 0,              // Total error count
  "total_formulas": 42,           // Number of formulas in file
  "error_summary": {              // Only present if errors found
    "#REF!": {
      "count": 2,
      "locations": ["Sheet1!B5", "Sheet1!C10"]
    }
  }
}
```

## Best Practices

### Vendored dependencies (openpyxl)
This Skill vendors `openpyxl` (and dependencies) under `skills/xlsx/vendor/*.whl`. If importing `openpyxl` fails in a minimal runtime, prepend those wheels to `sys.path` (or import `skills/xlsx/recalc.py` which already bootstraps them).

### Networking in sandboxed environments
Some environments set `HTTP(S)_PROXY` that may reset connections. For simple downloads with Python, explicitly bypass proxies when needed:

```python
import urllib.request

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(url, timeout=60) as r:
    data = r.read()
```

Also note that some sites (notably `imf.org`) may return 403 unless you use browser-like headers. A robust pattern is:

```python
import urllib.request

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.imf.org/external/datamapper/",
    "Origin": "https://www.imf.org",
}

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
req = urllib.request.Request(url, headers=headers)
with opener.open(req, timeout=60) as r:
    data = r.read()
```

(Do not hardcode task-instance outputs; this is only for connectivity and reusable fetching.)

### Large worksheets / huge used ranges
Workbooks can contain sheets with extremely large `max_row/max_column` due to formatting (even if only a small area has data). Avoid iterating the entire sheet via `iter_rows()` unless you cap the range or use targeted coordinates.

### Library Selection
- **openpyxl**: Best for complex formatting, formulas, and Excel-specific features (and is usually available via the vendored wheels)
- **pandas**: Optional; often unavailable in minimal runtimes

### Working with openpyxl
- Cell indices are 1-based (row=1, column=1 refers to cell A1)
- Use `data_only=True` to read calculated values: `load_workbook('file.xlsx', data_only=True)`
- **Warning**: If opened with `data_only=True` and saved, formulas are replaced with values and permanently lost
- For large files: Use `read_only=True` for reading or `write_only=True` for writing
- Formulas are preserved but not evaluated - use recalc.py to update values

### Working with pandas (optional)
Only use `pandas` after you have verified it imports successfully in the current runtime (e.g., `try: import pandas as pd`). Do not rely on it for required workflows.

## Code Style Guidelines
**IMPORTANT**: When generating Python code for Excel operations:
- Write minimal, concise Python code without unnecessary comments
- Avoid verbose variable names and redundant operations
- Avoid unnecessary print statements

**For Excel files themselves**:
- Add comments to cells with complex formulas or important assumptions
- Document data sources for hardcoded values
- Include notes for key calculations and model sections
