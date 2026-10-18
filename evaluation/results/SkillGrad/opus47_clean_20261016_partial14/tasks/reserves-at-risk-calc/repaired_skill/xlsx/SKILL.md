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

## Plan Per Row Before Writing

For any multi-row calculation (STEPs with multiple formula rows, multi-row
templates, multi-column cross-sheet pulls), **plan one row at a time**.
Each formula row carries its own interpretive choices (which upstream
cell to consume, whether a lookup drives membership, which label a
"replicate X" phrase matches); planning per batch collapses those
choices and bypasses every per-row rule in this skill.

1. Before each formula-row write, emit the per-row artifacts that row
   requires: (a) **formula-family classification line** naming the
   surrounding formula's family and the family's σ-periodicity
   convention; (b) candidate-enumeration comment; (c) dependency-map
   entry; (d) **row-index-to-period verification line** when any cell
   reference depends on a row index whose year / period must be known
   (e.g. `Value!row 18 → confirmed via Value col A: "2025"`);
   (e) sequencing plan for lookup-driven membership; (f) label-scan
   note for "replicate X from Step N" phrasing.
2. If a Python block contains more than one `sheet[...] = ...` for a
   formula row, every such line must have its own per-row plan
   comment immediately above it. A single pre-STEP comment covering
   several rows does NOT satisfy this rule.
3. If per-row artifacts are missing, split the block or abort and
   re-plan — do not run recalc, do not save.

```python
# Generic shape — one plan comment per formula row:

# Row R1 plan:
#   Family: <VaR shock | carry/return | option vega | covariance | direct>
#     → σ convention: <annualized | period-matched | n/a>
#   Row-index verification: <sheet>!row <N> → confirmed via col A/B label "<Y>"
#   Candidates: <A>, <B>; Chosen: <X>; Reason: <picker rule>
sheet['<ref_R1>'] = '=<formula_R1>'

# Row R2 plan: <membership rule, sequencing: write-all → lookup → delete>
sheet['<ref_R2>'] = '=<formula_R2>'

# Row R3 plan: <"replicate X from Step N" → label-scan result>
sheet['<ref_R3>'] = f'={source_ref_matched_by_label_scan}'
```

Decision rule: if more than one formula row is being written and the
trace shows only one block-level planning comment — OR a per-row
comment is missing the formula-family line or the row-index
verification line when applicable — the per-row rules were not
enforced. Rewrite with a complete plan comment per row before
continuing.

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

#### Trace the Labeled Dependency Chain Before Coding

**Trigger.** Fires when (a) the task phrasing contains any ambiguity-signal
word — *exposure*, *shock*, *annualized*, *near-term*, *monthly*,
*quarterly*, *N-period X*, *volatility applied to*, *latest*, *most
recent*, *replicate X from Step N* — OR (b) the template defines any
labeled intermediate cell upstream of the cell you are about to write,
OR (c) the current STEP writes more than one formula referencing
upstream labeled cells. When fired, the artifacts below are **required
per formula row** (see "Plan Per Row Before Writing").

**Picker priority** when choosing which upstream cell a downstream formula
consumes — apply in order, stop at the first unique match:

0. **Formula-family classification (primary).** Before any label match,
   classify the surrounding formula shape and import that family's
   σ-periodicity convention:
   - `reserves × Z × σ`, `position × Z × σ`, any `Z × σ × V` shape
     → **VaR shock** → σ is **ANNUALIZED by domain convention**, regardless
     of any horizon qualifier in the task phrase. The horizon qualifier
     describes the exposure's horizon, not σ's periodicity.
   - `position × σ_period` with NO Z-score factor
     → **carry / return** → σ is **period-matched** to the position's
     period.
   - `vega × σ × √t`, `delta × σ × √t`
     → **option greek** → σ is **ANNUALIZED**.
   - `ρ × σ_a × σ_b`, `cov(a,b)` product
     → **covariance product** → both σs **ANNUALIZED**.
   - Direct arithmetic with no σ factor → family rule N/A; proceed to
     rule 1.
   When the family uniquely determines σ periodicity, rules 1–3 become
   **tiebreakers** among candidates of the family-compatible periodicity.
1. **Horizon-qualifier label match (tiebreaker).** Among the
   family-compatible candidates, if the downstream task phrase contains
   a horizon qualifier (*near-term*, *monthly*, *quarterly*, *annual*,
   *N-period*), the chosen cell's LABEL contains the matching qualifier.
   **Rebuilding the matched quantity by applying a scaling factor
   (`× √(k/K)`, `/ √(K/k)`) to a mismatched cell is a hard reject** —
   reference the label-matched cell directly.
2. **Oracle match (secondary, MANDATORY in the irreducible-ambiguity
   case).** If a reference value exists (template pre-fill, example cell,
   expected row), compute each candidate and keep the one matching
   within tolerance. **Mandatory** whenever the family is VaR shock AND
   both raw and annualized labeled σ cells exist upstream — this is the
   case where family-convention and horizon-qualifier literalism can
   conflict; literalism alone is insufficient. If no oracle is available
   in that case, surface the conflict explicitly in the plan comment
   rather than committing silently.
3. **Orphan-avoidance (tiebreaker only).** Prefer consuming a labeled
   intermediate ONLY when exactly one candidate remains after rules
   0–2. When the upstream STEP defines two or more labeled cells in the
   same semantic family (e.g. raw σ AND annualized σ), orphan-count is
   symmetric and this rule MUST NOT be invoked.

**Required artifacts (per formula row):**

1. **Formula-family + row-index comment** (before writing).
2. **Candidate-enumeration comment** (before writing). List ≥ 2
   candidates; `Reason` cites which picker rule chose the winner.
3. **Intermediate-to-consumer mapping** (before writing). For each
   labeled upstream cell, name the downstream consumer OR mark
   `ALLOWED ORPHAN` when no downstream phrase label-matches it AND the
   family convention does not point to it.
4. **Post-write orphan scan** (after writing). Cells marked
   `consumed by X` must appear textually in that formula.

```python
# Required artifact pattern (generic — adapt refs to the task):
# AMBIGUITY: "<task phrase>"
# Family: <VaR shock | carry/return | option greek | covariance | direct>
#   → σ convention: <annualized | period-matched | n/a>
# Horizon qualifier in phrase: <near-term|annualized|...|none>
#   (describes exposure horizon when family=VaR; describes σ period when family=carry)
# Row-index verification (if row index names a year/period):
#   <sheet>!row <N> → confirmed via col A/B label "<Y>"
# Candidates (restricted to family-compatible periodicity):
#   A = <expr>   # upstream label: "<label A>"
#   B = <expr>   # upstream label: "<label B>"
# Chosen: <X>
# Reason: rule 0 family convention + rule 1 label-text match
#         (or rule 2 oracle match on reference value <v>)
#
# Dependency map:
# <upstream_A> (<label A>) → consumed by <downstream_ref>
# <upstream_B> (<label B>) → ALLOWED ORPHAN (family mismatch; standalone statistic)
sheet['<downstream_ref>'] = '=<reserves_ref> * <Z_ref> * <upstream_X> / 100'
```

Decision rule: when the surrounding formula is `Z × σ × V` (VaR shock),
the σ cell must be the one labeled *annualized* — any horizon qualifier
("near-term", "3-month", "monthly") in the task phrase describes the
exposure's horizon, not σ's periodicity. If both raw and annualized σ
cells are present upstream, the oracle check (rule 2) is mandatory.
Rebuilding one σ from the other via a scaling factor remains a hard
reject in either direction.

Read `references/dependency-chain.md` when the trigger above fires and
any of these is true: (a) the upstream STEP defines two or more labeled
cells in the same semantic family; (b) the surrounding formula is a
VaR shock or option greek (family convention applies); (c) the task
phrase is "replicate X from Step N" and no Step-N row is literally
labeled X; (d) the task phrase contains "latest" / "most recent" and
the source file has an unknown last non-null row; (e) a formula
references a cell by row index whose year / period must be known. That
chapter contains the Formula Family Index, the full picker-priority
procedure, the mandatory oracle-check branch, the row-index-to-period
verification sub-rule, the "replicate-X label-scan" sub-rule, the
"latest = source last-non-null" sub-rule, and worked examples
including the σ-rebuilding and horizon-literalism anti-patterns. Skip
when the formula is a direct one-step calculation with no labeled
intermediates and no ambiguity-signal phrases.

#### Enumerate Set Membership From Source Data

When a formula or output depends on *which* items belong to a set,
**derive the set programmatically from the authoritative source** — do
not eyeball a header, do not hard-code the member list, do not accept
a truncated dump as review, and when the task names an in-sheet lookup
as the drop/keep mechanism, do not pre-filter the candidate set in
Python before writing.

1. Dump the full relevant rows / column headers with truncation disabled
   (pandas `display.max_columns=None`, `display.width=None`) or iterate
   per-cell. A dump containing `...` is not a valid review.
2. Construct the set with an explicit predicate over the dump
   (set-difference, non-null filter, lookup-returns-nonzero).
3. For drop / keep logic, express the condition as a predicate over the
   actual lookup result and PRINT the result for every candidate before
   committing. A hard-coded kept / dropped list variable
   (e.g. `kept = ["X", "Y"]`) is forbidden unless it is the output of a
   predicate expression computed in the current run.
4. **When the task names an in-sheet lookup (XLOOKUP, INDEX+MATCH,
   VLOOKUP) as the drop/keep mechanism**, honor the sequencing:
   (a) write ALL candidate rows / columns into the sheet first;
   (b) write the lookup formula for every candidate;
   (c) run recalc; (d) THEN delete the rows / columns whose lookup
   returned no data. The delete is a post-recalc cleanup inside the
   workbook — never a pre-write Python prune.
5. For wildcard / partial-string lookups (`MATCH("*s*", ...)`,
   `.DESC`-row lookups), print the full result row for every candidate
   — wildcard matches collide or miss silently.

```python
# Generic set-membership derivation (adapt sheet/column names):
import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

headers_a = [c.value for c in sheet_a[header_row]]
headers_b = [c.value for c in sheet_b[header_row]]
members_a = {h for h, v in zip(headers_a, sheet_a[data_row]) if v.value is not None}
members_b = {h for h, v in zip(headers_b, sheet_b[data_row]) if v.value is not None}
additional = sorted(members_b - members_a)   # explicit predicate
print("additional members:", additional)

# Drop/keep from lookup result, not a hard-coded list:
kept = [name for name in candidates
        if lookup_result(name) not in (None, 0, "#N/A")]
print("kept:", kept)
```

Decision rule: if the written code contains a literal list of member
names that was not assigned from a predicate in this run, OR the dump
output contains an ellipsis, OR a lookup-driven drop was executed in
Python before the lookup formula was written into the sheet, the set
is unverified — recompute from a non-truncated dump + predicate, or
restore all candidates and let the sheet's lookup run before deleting.

Read `references/set-membership.md` when (a) a wildcard / partial-string
lookup drives the drop/keep decision, (b) the candidate set is wide
enough that a dump may truncate, (c) the code contains a literal member
list, or (d) the task describes a drop/keep rule driven by an in-sheet
lookup and the sequencing (write-all → lookup → delete) must be
preserved. Skip when the set is a small fixed enumeration explicitly
stated in the task text.

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
     - `#NAME?`: Unrecognized formula name — the recalc engine (LibreOffice)
       may not accept the Excel 2010+ dotted name. Try the legacy
       equivalent BEFORE considering any other fix:
       `NORM.S.INV` → `NORMSINV`, `NORM.INV` → `NORMINV`,
       `NORM.S.DIST` → `NORMSDIST`, `NORM.DIST` → `NORMDIST`,
       `STDEV.S` → `STDEV`, `STDEV.P` → `STDEVP`,
       `VAR.S` → `VAR`, `VAR.P` → `VARP`,
       `COVARIANCE.S` → `COVAR`, `PERCENTILE.INC` → `PERCENTILE`,
       `QUARTILE.INC` → `QUARTILE`. **Do NOT resolve `#NAME?` by
       replacing the formula with a hardcoded numeric value** — that
       violates the "formulas not hardcoded values" rule and often
       violates a task-stated "use Excel for computation" constraint.
       Hardcoding is only acceptable when the task explicitly permits it
       for that cell and must carry a source comment.

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
- [ ] **Per-row plan comment present for every formula row**: Each `sheet[...] = ...` for a formula row has its own plan comment above it, including the formula-family / σ-convention line, the candidate-enumeration + dependency map, and (when applicable) the row-index-to-period verification. A single pre-STEP block covering multiple rows does not satisfy this check.
- [ ] **Formula family classified and the family's σ convention named in the plan comment**: For every formula containing a σ factor, the plan comment states the family (VaR shock → annualized σ; carry/return → period-matched σ; option greek → annualized σ; covariance → annualized σ) and the chosen σ cell is of the family-compatible periodicity. See `references/dependency-chain.md`.
- [ ] **Labeled σ picked by family convention first, horizon qualifier as tiebreaker**: In a `Z × σ × V` VaR shock, σ is annualized regardless of a "near-term" / "monthly" / "3-month" phrase — the phrase qualifies the exposure horizon, not σ. When both raw and annualized σ cells exist upstream in a VaR shock, the oracle check is mandatory. See `references/dependency-chain.md`.
- [ ] **Every row-index-to-year / row-index-to-period reference verified against THAT sheet's own label column**: Do not transfer a row-index-to-year mapping by analogy from another sheet in the same workbook — different sheets may have different row layouts. Record each verification in the per-row plan comment (e.g. `Value!row 18 → confirmed via Value col A: "2025"`).
- [ ] **Set membership derived from source data via the mechanism the task names**: Any set the output depends on (countries, columns, rows to include/drop) comes from a non-truncated dump + explicit predicate. When the task names an in-sheet lookup as the drop/keep mechanism, the lookup is written for every candidate inside the sheet BEFORE any delete happens. See `references/set-membership.md`.

### Common Pitfalls
- [ ] **NaN handling**: Check for null values with `pd.notna()`
- [ ] **Far-right columns**: FY data often in columns 50+
- [ ] **Multiple matches**: Search all occurrences, not just first
- [ ] **Division by zero**: Check denominators before using `/` in formulas (#DIV/0!)
- [ ] **Wrong references**: Verify all cell references point to intended cells (#REF!)
- [ ] **Cross-sheet references**: Use correct format (Sheet1!A1) for linking sheets
- [ ] **σ periodicity picked by surface cue instead of formula-family convention**: The downstream σ cell was chosen by matching the task phrase's horizon qualifier ("near-term" → raw σ) or by orphan-avoidance ("consume the labeled annualized cell"), without first classifying the surrounding formula shape. Variants: (a) VaR shock `Z × σ × V` picked raw σ because phrase said "near-term" — VaR convention requires annualized σ; (b) consumed annualized σ when the formula is a period-matched carry/return; (c) rebuilt one σ from another via `×√(k/K)` or `/√(K/k)` scaling instead of referencing the family-compatible labeled cell; (d) "replicate X from Step N" copied by position instead of label-scan; (e) "latest" / "most recent" taken from a template date label rather than source's actual last non-null row. All share the mechanism: pick by domain convention + label-text match, not by surface cue or position. See `references/dependency-chain.md`.
- [ ] **Row-index-to-period mapping transferred by analogy across sheets**: A row index whose year / period mattered (e.g. "`Value!row 18 is 2025`") was accepted from another sheet's layout without reading THAT sheet's own column A / B label. Row layouts need not agree between sheets — verify each sheet independently and record the verification in the plan comment.
- [ ] **Membership decided outside the mechanism the task names**: A literal `kept = [...]` list, a dump output with `...`, a wildcard lookup result not printed row-by-row, OR a Python pre-filter that removed candidate rows/columns before the task's in-sheet lookup had a chance to run — all are unverified. For in-sheet-lookup-driven drops: write all candidates, let the sheet lookup, delete after recalc. See `references/set-membership.md`.
- [ ] **`#NAME?` resolved by hardcoding instead of using a legacy function name**: Try the LibreOffice-compatible equivalent (`NORMSINV` for `NORM.S.INV`, etc.) before any hardcode. See the equivalents list under "Common errors to fix".

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
