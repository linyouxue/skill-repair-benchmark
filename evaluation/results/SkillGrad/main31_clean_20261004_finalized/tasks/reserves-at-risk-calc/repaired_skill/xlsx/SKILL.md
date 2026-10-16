---
name: xlsx
description: "Create, edit, and analyze spreadsheets using formulas (not constants), preserving templates, validating units/ranges by inspection, and verifying zero formula errors via recalc.py before delivery."
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

# XLSX creation, editing, and analysis

## Overview

A user may ask you to create, edit, or analyze the contents of an .xlsx file. You have different tools and workflows available for different tasks.

## Important Requirements

**LibreOffice Required for Formula Recalculation**: You can assume LibreOffice is installed for recalculating formula values using the `recalc.py` script. The script automatically configures LibreOffice on first run

## Workflow: Inspect before you map

1. **Tooling preflight (completion gate):** run a *real* tool command that successfully (a) locates the workbook file, (b) opens it with `python3`, and (c) prints `sheetnames` plus a small preview of the destination area you will write.
2. **Recovery loop on error:** if any shell/tool call fails (bad flag, quoting, missing interpreter, malformed tool payload), *stop* and retry with a simpler known-good sequence until you regain a working inspection loop.
3. Identify which sheets/tables are sources vs destinations; do not write until you can point to the exact source ranges.
4. For wide tables, inventory the full axis you will later depend on (e.g., scan the entire year row or the entire metric column), not just a visible sample.
5. Derive inclusion sets (which series/countries/metrics belong) from observed non-empty cells and header labels, not from a presumed list.
6. Record any unit metadata (e.g., thousands vs millions, currency vs volume) and decide conversions before populating formulas.
7. When mapping a wide-table header to a key (e.g., country/series), prefer a stable tokenization (exact prefix before a delimiter) and avoid fuzzy stripping; match columns by exact key/prefix rather than wildcards.
8. **Spec-disambiguation gate (labels like “3M vol”, “annualized”, “returns”):** before writing formulas, inspect the template for an existing definition, example numbers, or notes; if the convention is ambiguous, compute competing definitions in helper cells and choose the one that matches template evidence.

```python
# Preflight inspection: confirm you can open the workbook and see what to edit
from openpyxl import load_workbook

wb = load_workbook("input.xlsx", data_only=False)
print(wb.sheetnames)

ws = wb[wb.sheetnames[0]]
print("used range rows/cols:", ws.max_row, ws.max_column)
print("A1:D5:", [[c.value for c in r] for r in ws["A1:D5"]])
```

Read references/tooling-preflight-and-file-discovery.md when you cannot locate/open the workbook or any tool call fails before inspection completes. Skip when you have already opened the workbook and printed `sheetnames` in the current run.

Read references/inventory-wide-table-and-units.md when the output requires selecting a subset of series/countries from a wide sheet and/or converting units. Skip when the input already provides an explicit, fixed list of keys and units.

Read references/keyed-mapping-and-deletion-semantics.md when the workbook requires building a key list from one step and then applying a later “delete/exclude missing” rule while preserving order/alignment across downstream formulas. Skip when the later step is a pure filter output and downstream cells do not rely on positional alignment.

Read references/volatility-definition-and-annualization.md when the workbook asks for a volatility and an “annualized” volatility but the definition/scaling is not explicitly spelled out in-cell. Skip when the template already contains the exact volatility and annualization formulas you must replicate.

## CRITICAL: Use formulas, not hardcoded calculations

**Always use Excel formulas instead of calculating values in Python and hardcoding them.** This ensures the spreadsheet remains dynamic and updateable.

- Never replace a required derived formula with a numeric constant to “avoid compatibility issues”.
- If a function is incompatible, rewrite into an equivalent Excel-compatible expression (possibly using more primitive operators/functions) and verify via recalc.py that there are zero formula errors.

```python
# openpyxl writes formulas as strings; keep the workbook dynamic
from openpyxl import load_workbook

wb = load_workbook("input.xlsx")
ws = wb.active

ws["B2"] = "=A2*B1"   # formula (not a constant)
ws["C2"] = "=IFERROR(B2,\"\")"  # guard against errors

wb.save("output.xlsx")
```

## Common Workflow
1. **Choose tool**: pandas for data, openpyxl for formulas/formatting
2. **Create/Load**: Create new workbook or load existing file
3. **Modify**: Add/edit data, formulas, and formatting
4. **Save**: Write to file
5. **Recalculate formulas (MANDATORY IF USING FORMULAS)**: Use the recalc.py script
   ```bash
   python3 recalc.py output.xlsx
   ```
6. **Verify and fix any errors**:
   - If `status` is `errors_found`, fix the identified cells and recalc again.

## Reading and analyzing data

### Data analysis with pandas
For data analysis, visualization, and basic operations, use **pandas** which provides powerful data manipulation capabilities:

```python
import pandas as pd

df = pd.read_excel("file.xlsx")
all_sheets = pd.read_excel("file.xlsx", sheet_name=None)

preview = df.head()
summary = df.describe(include="all")

df.to_excel("output.xlsx", index=False)
```

## Creating new Excel files

```python
from openpyxl import Workbook

wb = Workbook()
ws = wb.active

ws["A1"] = "Header"
ws.append([1, 2, 3])
ws["D2"] = "=SUM(A2:C2)"

wb.save("output.xlsx")
```

## Editing existing Excel files

```python
from openpyxl import load_workbook

wb = load_workbook("existing.xlsx")
ws = wb[wb.sheetnames[0]]

ws["A1"] = "New Value"
ws.insert_rows(2)

wb.save("modified.xlsx")
```

## Recalculating formulas

```bash
python3 recalc.py <excel_file> [timeout_seconds]
```

## Common Pitfalls
- Proceeding without a successful workbook inspection/tool run (e.g., using `python` when only `python3` exists, shell quoting errors, or not retrying after a tool error), which leads to no edits or edits to the wrong places.
- Sampling a few visible columns/rows in a wide table and then hard-coding a key list or cell addresses instead of inventorying the full axis you depend on.
- Converting units (e.g., volume→value) without first reading the unit metadata and applying the correct scale factor.
- Using fuzzy key parsing or wildcard header matching that can conflate similar series and pull values from the wrong columns.
- Implementing an exclusion rule (“delete countries with missing data”) by only blanking a tail segment, which breaks positional alignment for downstream formulas that expect “Step N equals Step M minus excluded keys, preserving order.”
- Treating ambiguous labels (e.g., “3M volatility”, “annualized”) as self-defining; instead disambiguate by inspecting template evidence and reconciling competing definitions.
- Replacing required Excel formulas with constants; instead rewrite to a compatible equivalent and validate with recalc.py.
- Opening with `data_only=True` and saving, which permanently replaces formulas with values.
