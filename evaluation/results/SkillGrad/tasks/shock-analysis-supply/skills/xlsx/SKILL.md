---
name: xlsx
description: "Create, edit, and analyze spreadsheets with formulas, formatting, and verification using openpyxl/pandas plus LibreOffice recalc for validation."
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

## Workflow: finish within the iteration budget

1. **Start by opening the workbook** when a path to an `.xlsx` is provided; do not spend the early budget on analysis before the file is open.
2. **Write a step-bounded plan**: *open → inspect sheets/ranges → perform edits in small batches → save a working draft → recalc/verify → fix errors → final save → stop*.
3. **Micro-budget (enforce a pivot)**: within the first **1–2 tool calls** you must open the workbook; by **tool call ~5** you must have saved a working draft with at least one required edit (a seed formula/link, a populated range, or a structural placeholder that will be filled in).
4. **Progress checkpoints (mandatory self-audit)**: after tool call **2** and again after **5**, ask:
   - *Is the workbook open in my code right now?*
   - *Have I saved a draft that includes at least one required edit?*
   If either answer is **no**, the **next action** must be: **load_workbook → write a seed edit → save draft** (stop analysis/browsing until this is true).
5. **Define “measurable progress”**: at least one of (a) workbook opened, (b) required sheets identified, (c) cells/formulas written, (d) output file saved.
6. **Hard guardrail (no silent exit)**: do not stop/`end_turn` until you have (i) opened the workbook and (ii) made at least one required edit (a seed formula/link, a populated range, or a saved draft).
7. **Pivot rule**: if you have made **no measurable progress by the micro-budget**, abort exploration and switch to direct workbook editing to produce the deliverable.

## Overview

A user may ask you to create, edit, or analyze the contents of an .xlsx file. You have different tools and workflows available for different tasks.

## Important Requirements

**LibreOffice Required for Formula Recalculation**: You can assume LibreOffice is installed for recalculating formula values using the `recalc.py` script. The script automatically configures LibreOffice on first run

## Reading and analyzing data

### Data analysis with pandas
For data analysis, visualization, and basic operations, use **pandas** which provides powerful data manipulation capabilities:

```python
import pandas as pd

df = pd.read_excel(path)
all_sheets = pd.read_excel(path, sheet_name=None)

preview = df.head()
summary = df.describe(include='all')

df.to_excel(out_path, index=False)
```

## Excel File Workflows

## CRITICAL: Use Formulas, Not Hardcoded Values

**Prefer Excel formulas over calculating in Python and hardcoding results** so the workbook stays dynamic and recalculates when inputs change.

```python
from openpyxl import load_workbook

wb = load_workbook(path)
ws = wb.active

ws['A1'] = 1
ws['A2'] = 2
ws['A3'] = '=SUM(A1:A2)'

wb.save(out_path)
```

## Common Workflow
1. **Choose tool**: pandas for data, openpyxl for formulas/formatting
2. **Create/Load**: Create new workbook or load existing file
3. **Modify**: Add/edit data, formulas, and formatting
4. **Save**: Write to file
5. **Recalculate formulas (MANDATORY IF USING FORMULAS)**: `python recalc.py <excel_file>`
6. **Verify and fix any errors** (locations + error types) and recalc again

### Creating new Excel files

```python
from openpyxl import Workbook

wb = Workbook()
ws = wb.active

ws.append(['col1', 'col2'])
ws.append([1, 2])
ws['C2'] = '=A2+B2'

wb.save(out_path)
```

### Editing existing Excel files

```python
from openpyxl import load_workbook

wb = load_workbook(path)
ws = wb[wb.sheetnames[0]]

ws['A1'] = 'Updated'
ws['B1'] = '=A1'

wb.save(out_path)
```

## Recalculating formulas

Excel files created or modified by openpyxl contain formulas as strings but not calculated values. Use the provided `recalc.py` script to recalculate formulas:

```bash
python recalc.py <excel_file> [timeout_seconds]
```

## Common Pitfalls
- Burning the iteration budget on analysis/search before opening the workbook and making any edits (always get a saved working draft early).
- Hardcoding computed outputs in Python instead of writing Excel formulas.
- Saving a workbook after loading with `data_only=True` (can destroy formulas).
- Skipping recalc/verification after editing formulas, leaving hidden #REF!/#DIV/0! errors.
