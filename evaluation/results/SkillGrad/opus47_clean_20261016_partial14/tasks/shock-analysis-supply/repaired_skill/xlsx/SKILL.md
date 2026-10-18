---
name: xlsx
description: "Create, edit, and analyze spreadsheets (.xlsx, .xlsm, .csv, .tsv). Covers formulas, formatting, data analysis, visualization, template editing, Excel-feature tasks (Solver, Goal Seek), and recalculating workbooks produced by openpyxl."
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

**Headless pipeline limits — read before scaffolding Solver / dynamic features**: `wb.save` and `recalc.py` (LibreOffice headless) evaluate FORMULAS. They do NOT execute Excel Solver, Goal Seek, Data Table, macros, or any other GUI-driven feature. Any cell whose value is normally produced by one of those features will be delivered to the grader with whatever Python wrote (an initial guess, `=NA()`, or blank). For every such cell, Phase A must write BOTH the surrounding formulas AND a numerically pre-computed value into the solver-target cell itself — see `Excel Solver / Goal Seek / Data Table tasks`.

## Scaffold the workbook BEFORE acquiring any live data

If the task combines a workbook model (formulas, cross-sheet links, Solver wiring, table structure, downstream calculations) with online data acquisition, the two workstreams are orthogonal. Phase A (model scaffold) is network-independent and MUST be completed before Phase B (acquisition) begins. Serializing "acquire first, then model" is the dominant failure mode on these tasks: when acquisition blocks (bot challenges, 404s, late-install hangs), nothing gets written. A workbook with every formula wired and only raw cells left as `=NA()` scores far higher than a workbook with one raw column populated and no formulas.

Two-phase ordering:

1. **Phase A — scaffold (offline, zero network).** Inspect every sheet of the template, enumerate every non-raw cell (formulas, links, Solver changing/objective cells, table headers, downstream calculations), and write them all. Where a raw input would land, write `=NA()` (or leave blank with a `pending:` comment). For Solver changing cells, ALSO write a numerical pre-fill (see headless-limits note above). Save; verify mtime changed.
2. **Phase B — acquire (online).** Only after Phase A is saved, begin fetches under the per-source time-box in `Plan + time-box Phase B acquisition`. Each landed source overwrites its placeholders.

**Mechanical gate (executed as code, not advisory).** At iteration `ITER_BUDGET // 3` (e.g. iter 20 of 60), call `phase_a_complete(iter_counter, output_path, MIN_FORMULA_COUNT)`. If it returns `DEADLINE_MISSED`, STOP all acquisition work and finish Phase A before any further fetch. The grader rewards structural completeness; one landed raw column with no formulas around it scores near zero.

```python
import os
from openpyxl import load_workbook

PRE_TASK_MTIME     = os.path.getmtime(output_path)
ITER_BUDGET        = 60
SCAFFOLD_DEADLINE  = ITER_BUDGET // 3          # ~iter 20 of 60

# Phase A write — scaffold is a list of (sheet, coord, value, kind)
wb = load_workbook(output_path)
for sheet, coord, value, kind in scaffold:
    wb[sheet][coord] = value                   # formula, =NA() placeholder, or Solver pre-fill
wb.save(output_path)
assert os.path.getmtime(output_path) != PRE_TASK_MTIME

# At iter SCAFFOLD_DEADLINE, run the gate — do NOT skip, do NOT treat as prose
status = phase_a_complete(iter_counter, output_path, MIN_FORMULA_COUNT)
if status == "DEADLINE_MISSED":
    # STOP acquisition entirely; finish Phase A before any further fetch
    pass
```

Read references/scaffold-before-acquire.md when the task couples an Excel model with any online acquisition step. The chapter owns the scaffold-write-list builder (including Solver changing-cell pre-fills), the `phase_a_complete` gate implementation with its corrective branch, the placeholder-overwrite pattern for Phase B, a worked Phase-A example spanning depreciation, link-formula columns, Solver-driven smoothing cells, and a downstream calibration table, and the Phase-A verification assertion. Skip when the task is pure data acquisition with no formulas, or pure modelling with all inputs supplied in the prompt.

## Plan + time-box Phase B acquisition

This section governs Phase B only — see `Scaffold the workbook BEFORE acquiring any live data` for the Phase A prerequisite. Within Phase B, the failure mode is burning the remaining budget on one blocked source while other sources go unfetched. The per-source time-box prevents that.

Minimum plan, written as code at the start of Phase B:

1. Record `PHASE_B_START_MTIME = os.path.getmtime(output_path)` (Phase A already touched the file) and the remaining `ITER_BUDGET`.
2. List every data source with a per-source iteration budget (default ≤ 5, hard cap) and the target cells/sheet it populates. Order easiest-first.
3. Fix checkpoint iteration numbers at ~1/6, ~1/3, and 1/2 of the remaining budget. At each checkpoint, if no new source has landed since the last checkpoint, pivot (early checkpoints) or abandon acquisition and flush partial (halfway).
4. After each source lands, immediately `load_workbook` → overwrite its `=NA()` placeholders → `save` → read one cell back. Do not batch writes to the end.
5. When a source exceeds its per-source budget, STOP it, write `pending: <source>; <reason>` on its first target cell, and move on. Do NOT try another header/cookie/mirror variation on a blocked endpoint.
6. Never start a heavy install (browser engine, new conda env, source-built package) in the last 20% of the budget.
7. If a terminal tool call returns "Cannot execute multiple commands at once", the call chained commands (`;`, `&&`, newline-joined). Split into separate single-command tool calls and retry — do NOT re-attempt with the same chained form.

```python
import os
from openpyxl import load_workbook
from openpyxl.comments import Comment

PHASE_B_START_MTIME = os.path.getmtime(output_path)
PER_SOURCE_BUDGET = 5

def flush(cells_to_write, source_label, target_sheet):
    wb = load_workbook(output_path)
    ws = wb[target_sheet]
    for coord, value in cells_to_write.items():
        ws[coord] = value              # overwrites =NA() placeholder
    first = next(iter(cells_to_write))
    ws[first].comment = Comment(f"Source: {source_label}", "acquisition")
    wb.save(output_path)
    assert os.path.getmtime(output_path) != PHASE_B_START_MTIME

def checkpoint_halfway(iter_counter, halfway):
    if iter_counter >= halfway and os.path.getmtime(output_path) == PHASE_B_START_MTIME:
        return "ABANDON_ACQUISITION_FLUSH_PARTIAL"
    return "CONTINUE"
```

Decision rule: at the halfway iteration mark of Phase B, if no raw source has landed, abandon the current fetch, write whatever partial data is in hand (even guesses or one landed source), mark the rest `pending:`, and stop acquisition.

Read references/time-boxed-acquisition.md BEFORE the first fetch attempt in Phase B. The chapter owns the full plan template, the per-source counter pattern, the numbered checkpoint actions, the named-blocker catalog (dataverse.nl Anubis, Edgesuite Access Denied, Playwright install hang) with the specific pivot for each, and the terminal "multiple commands at once" recovery. Skip when all inputs are supplied in the prompt or the template itself.

## Inspect provided templates before writing

When the task supplies a workbook template, every column, row, and header already encodes expected semantics (which variable goes where, units, year range). Inspection output is not just a mental model — it IS the Phase-A scaffold write list: every non-raw cell addressed by coordinate with its formula or `=NA()` placeholder.

Before writing a single value:

1. `load_workbook(path)` and iterate `wb.sheetnames` — open EVERY sheet, including any `Notes`, `README`, `Metadata`, or `Definitions` sheet.
2. For each column/row you intend to fill, record: exact header text, implied units (ratio vs index vs currency scale), year/row range, and any variable-name hint in the header.
3. If the mandated source ships its own metadata/variable-definitions sheet, open and read it — pick which source variable fills each template column from the metadata, not from a guess.
4. Emit the scaffold write list: every formula, link, Solver cell, and table-structure cell is one entry; every raw-input cell is a `=NA()` entry. This list drives Phase A directly.

```python
from openpyxl import load_workbook
wb = load_workbook(template_path)
scaffold = []
for name in wb.sheetnames:
    ws = wb[name]
    headers = [ws.cell(row=header_row, column=c).value
               for c in range(1, ws.max_column + 1)]
    # for each cell to fill, append either a formula entry or a =NA() placeholder
```

Decision rule: if the template header implies units different from the raw source (e.g. header says millions, source gives units), add an Excel cell comment on the first data cell showing the conversion factor explicitly.

Read references/template-inspection.md when the template has multiple sheets, a metadata/notes sheet, or when you must choose which source variable fills a given template column. Skip when creating a brand-new workbook with no supplied template.

## Honor mandated data sources and tools

When the task names a specific data source (a URL, a named dataset release, a specific vintage) and/or a specific acquisition tool (Playwright MCP browser, a named Python/R package, an API), those names are binding. The common failure is: the easy path breaks (404, timeout, parse error) and the executor silently substitutes typed-in values from memory, often with a false provenance claim.

Rules:

- A 404 or parse failure on a direct URL is NOT a license to hardcode. It is a trigger to escalate to the mandated fallback (e.g. Playwright MCP browser) or to actually extract from the named package.
- Never cite a source you did not actually open. If you claim "from package X" or "from URL Y", the extraction/fetch must have happened in this run.
- Every raw-data cell written from an external source MUST carry an Excel cell comment naming the exact source actually used (URL + access date, or package name + version + file path inside the archive).
- When the mandated dataset ends before the required horizon, do NOT fill the gap with CAGR, linear interpolation, or any other convenience formula. Check for a newer vintage; check for a documented bridge/extension series; only if neither exists, leave the cells blank with a comment "source ends YYYY; no authoritative extension found".
- Each acquisition rung runs under the per-source iteration budget set during Phase B planning (see `Plan + time-box Phase B acquisition`). Exhausting the budget triggers the blocked-source fallback, not an extra rung.

```python
# Generic acquisition skeleton — exhaust mandated path before escalating
def acquire(source_spec):
    try:
        return direct_download(source_spec.url)        # 1. direct URL
    except (HTTPError, ParseError):
        pass
    try:
        return extract_from_named_package(source_spec)  # 2. named package / archive
    except (NotFound, ExtractError):
        pass
    return playwright_mcp_fetch(source_spec)            # 3. mandated browser path
    # 4. if all mandated paths fail: surface blocker; do NOT type values from memory
```

Read references/live-data-acquisition.md when the task names a specific online data source, a specific acquisition tool (Playwright MCP, a named package), or when the mandated source ends before the required horizon. Skip when all inputs are supplied in the task prompt or the template itself.

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

### Excel Solver / Goal Seek / Data Table tasks

When the task mandates an Excel-native solver feature (Solver, Goal Seek, Data Table, Scenario Manager), the workbook itself must contain the wiring AND the solver-target cells must ship with numerically pre-computed values. These two requirements sound contradictory but are not — they target different cells.

**Headless-pipeline fact.** `openpyxl.save` and `recalc.py` (LibreOffice headless) do NOT execute Solver, Goal Seek, Data Table, or any GUI-driven feature. The workbook is delivered to the grader with the solver-target cells (changing cells / "by changing" cell / Data-Table input cells) holding whatever Python wrote. A correctly-wired Solver area with changing cells left at `=NA()` or a trivial `=input_cell` guess ships with the objective evaluating to a degenerate value (zero, `#N/A`) — the grader sees "Solver was never run".

Therefore, for every Solver / Goal-Seek / Data-Table setup, Phase A writes BOTH:

1. **Changing / target cells (the ones the GUI feature would normally overwrite).** Compute the solve numerically in Python (closed-form linear solve, scipy.optimize, or a short iterative routine) and write the computed values into these cells as a pre-fill. Comment the first changing cell: "Solver changing cell — pre-filled with numerical solve; the GUI feature was not available in the headless pipeline". This is NOT the "pre-solve in Python" anti-pattern — those cells have NO formula of their own; something must write them.
2. **Objective / constraint / result cells (surrounding the solver target).** KEEP as live Excel formulas referencing the changing cells. The objective then evaluates to a non-degenerate number on `recalc.py`, and a human reviewer who re-runs Solver gets the same or improved answer.

```python
# Generic Solver wiring + numerical pre-fill (Phase A, before acquisition)
import numpy as np
from openpyxl.comments import Comment

# 1. Compute the solve numerically in Python
y          = np.array(observed_series)                 # input vector
trend_vals = numerical_solve(y, params)                # e.g. closed-form or np.linalg.solve

# 2. Write changing cells with the numerical pre-fill
for i, row in enumerate(data_rows):
    sheet.cell(row=row, column=changing_col).value = float(trend_vals[i])
sheet.cell(row=data_rows[0], column=changing_col).comment = Comment(
    "Solver changing cell — pre-filled with numerical solve "
    "(headless pipeline does not execute Solver)", "solver"
)

# 3. Objective and constraints remain live formulas referencing the changing cells
sheet[objective_cell] = f"=SUMPRODUCT({residual_range},{residual_range})"
for row in data_rows:
    sheet.cell(row=row, column=residual_col).value = (
        f"={input_col_letter}{row}-{changing_col_letter}{row}"
    )
```

Decision rule: open the saved file. The objective cell must evaluate (via `recalc.py`, data_only=True) to a non-zero, non-error numeric value. If it is `None`, `#N/A`, or zero when the input is non-zero, the changing cells are empty or at a degenerate guess — compute the numerical solve and re-write the pre-fill. If deleting the Python script and perturbing one input cell leaves the objective unchanged, the surrounding formulas are hardcoded — rewrite them as live formulas.

Read references/excel-solver-setup.md when the task names Excel Solver, Goal Seek, Data Table, or Scenario Manager, or when a step requires minimizing/maximizing an objective subject to constraints. The chapter owns the worked HP-filter-style example (numpy closed-form penalized least squares written to the changing cells, SUMPRODUCT objective as a live formula, residual constraint formulas), Goal-Seek/Data-Table/Scenario-Manager variants, and the perturb-and-recalc verification check. Skip when the computation is a straightforward formula chain with no optimization step.

## Common Workflow
1. **Inspect template & build scaffold list (Phase A planning)**: open every sheet, record headers/units, emit the scaffold write list of every non-raw cell with its formula or `=NA()` placeholder, and for every Solver/Goal-Seek/Data-Table target cell add its numerical pre-fill entry; see `Inspect provided templates before writing`
2. **Scaffold the workbook (Phase A write)**: write every formula, link, Solver changing-cell pre-fill, objective/constraint formula, and table-structure cell with `=NA()` where raw inputs will land; save; verify mtime changed and formula count meets the minimum.
3. **Mechanical scaffold-deadline gate (at iter `ITER_BUDGET // 3`)**: execute `phase_a_complete(iter_counter, output_path, MIN_FORMULA_COUNT)`. If it returns `DEADLINE_MISSED`, STOP all acquisition and return to step 2 until it returns `COMPLETE`. This is a code step, not advisory — do not skip because "acquisition is almost done".
4. **Acquire raw data (Phase B)**: run per-source time-box; see `Plan + time-box Phase B acquisition`
5. **Flush incrementally**: after each source lands, overwrite its `=NA()` placeholders and save
6. **Recalculate formulas (MANDATORY IF USING FORMULAS)**: Use the recalc.py script
   ```bash
   python recalc.py output.xlsx
   ```
   The script returns JSON with error details; if `status` is `errors_found`, check `error_summary` and fix. Common errors: `#REF!` (invalid refs), `#DIV/0!` (zero denominators), `#VALUE!` (wrong types), `#NAME?` (unrecognized functions).
7. **Final target-cell readback**: re-open with `load_workbook(output_path, data_only=True)` and iterate every target cell from the scaffold write list. Assert each holds a non-None, non-error value. `recalc.py` only reports formula errors — it does NOT catch empty Solver changing cells, blank raw cells, or `#N/A` cascades from `=NA()`. On any None / error, decide:
   - Raw-input cell with no landed data → leave as `=NA()` with a `pending: <source>` comment (acceptable final state).
   - Solver changing cell with no value → compute the solve numerically and write the pre-fill now; re-run step 6.
   - Formula cell cascading `#N/A` from `=NA()` upstream → acceptable if that raw input genuinely did not land; otherwise fix the upstream (land the raw value or pre-fill the Solver cell it depends on).

```python
# Step 7 — final target-cell readback
from openpyxl import load_workbook

ERROR_STRINGS = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}
wb = load_workbook(output_path, data_only=True)
missing, errored = [], []
for sheet, coord, _, kind in scaffold:
    if kind == "raw_placeholder":
        continue                                   # =NA() + pending comment is acceptable
    v = wb[sheet][coord].value
    if v is None:
        missing.append((sheet, coord, kind))
    elif isinstance(v, str) and v in ERROR_STRINGS:
        errored.append((sheet, coord, kind, v))
assert not missing,  f"empty target cells (fill numerically if Solver): {missing[:5]}"
assert not errored,  f"error target cells (fix upstream or pre-fill): {errored[:5]}"
```

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

## Formula Verification Checklist

Quick checks to ensure formulas work correctly:

### Essential Verification
- [ ] **Test 2-3 sample references**: Verify they pull correct values before building full model
- [ ] **Column mapping**: Confirm Excel columns match (e.g., column 64 = BL, not BK)
- [ ] **Row offset**: Remember Excel rows are 1-indexed (DataFrame row 5 = Excel row 6)
- [ ] **Phase A complete at mechanical gate**: at iter `ITER_BUDGET // 3`, `phase_a_complete` returns `COMPLETE` — every formula/link/Solver changing-cell pre-fill/objective/constraint/table-structure cell is written and saved; only raw-input cells are `=NA()` or `pending:`. If `DEADLINE_MISSED`, STOP acquisition and finish Phase A — see `Scaffold the workbook BEFORE acquiring any live data`.
- [ ] **Final data_only readback**: after `recalc.py`, every non-placeholder target cell holds a non-None, non-error value when re-opened with `data_only=True`. See Common Workflow step 7.

### Common Pitfalls
- [ ] **NaN handling**: Check for null values with `pd.notna()`
- [ ] **Far-right columns**: FY data often in columns 50+
- [ ] **Multiple matches**: Search all occurrences, not just first
- [ ] **Division by zero**: Check denominators before using `/` in formulas (#DIV/0!)
- [ ] **Wrong references**: Verify all cell references point to intended cells (#REF!)
- [ ] **Cross-sheet references**: Use correct format (Sheet1!A1) for linking sheets
- [ ] **Unread template**: Values written before every sheet (including metadata/notes) was opened — causes wrong variable choice and wrong unit scaling
- [ ] **False provenance / silent hardcoding**: Values typed from memory after a mandated fetch failed; cell comments cite sources that were never actually opened
- [ ] **Convenience extrapolation**: Gaps between a dataset's end year and the required horizon filled with CAGR or linear-interp instead of locating a newer vintage or leaving cells blank with a provenance comment
- [ ] **Headless-pipeline degenerate Solver**: Solver changing cells shipped at `=NA()` or trivial-guess formulas with no numerical pre-fill; `wb.save` and `recalc.py` do NOT run Solver, so the objective ships evaluating to a degenerate value. Phase A must write a numerical pre-fill into every solver-target cell while keeping objective/constraints as live formulas — see `Excel Solver / Goal Seek / Data Table tasks`.
- [ ] **Acquisition serialized before model scaffold**: Executor treats raw-data fetch as a blocking prerequisite for any workbook writing, so when acquisition stalls (bot challenge, 404, late install, header-variation loop), every formula/link/Solver cell is also left unwritten. Covers both the "untouched output file at halfway" symptom and the "one raw column written, entire model blank" symptom. Trigger: at `ITER_BUDGET // 3`, run `phase_a_complete`; if `DEADLINE_MISSED`, abandon acquisition and finish scaffolding first.
- [ ] **No final data_only readback**: Agent stops after `recalc.py` reports no formula errors — but `=NA()` upstreams, empty Solver changing cells, and `#N/A` cascades all pass `recalc.py`. Always re-open with `data_only=True` and iterate target cells; see Common Workflow step 7.

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
