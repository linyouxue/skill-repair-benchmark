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

## Baseline deliverable before per-item tuning

When the workbook is populated from a batch of per-item work (OCR over
many images, parsing many files, scraping many pages, per-row heuristics),
the iteration budget disappears into tuning a few hard inputs unless you
ship a baseline first.

1. **Ship end-to-end before tuning.** Implement the simplest viable
   extractor over the *full* input set, write the workbook to the required
   output path, and confirm the file exists on disk before investing any
   iterations in edge cases. A deliverable with imperfect rows beats no
   deliverable.
2. **Re-save the full workbook between tuning cycles.** Each round of
   per-item tweaks ends with another full end-to-end run that overwrites
   the output file. Never leave the pipeline in a half-tuned state with no
   fresh save.
3. **Bound per-item tuning.** Cap effort on any single hard input (a few
   iterations), then accept the current result and move on. Measure
   aggregate accuracy, not single-item perfection, when deciding whether
   more tuning is worth remaining budget. **Bounded means a small positive
   number of attempts, not zero.** On a row your own reasoning has
   already flagged as wrong (`"074 still fails"`, `"X is corrupted"`,
   `"a couple of hard cases remain"`), one targeted re-extraction is
   mandatory before saving — see the "degenerate / known-wrong row"
   checklist bullet below.

```python
# Generic shape for batch extraction → xlsx
from pathlib import Path
from openpyxl import Workbook

def extract_one(item):           # simplest viable per-item logic
    return simple_parse(item)

def build_workbook(items, out_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["id", "value"])
    for item in items:
        ws.append([item.id, extract_one(item)])
    wb.save(out_path)

out = Path("/app/workspace/output.xlsx")
build_workbook(load_all_items(), out)
assert out.exists(), f"baseline not written to {out}"  # verify save
# Only now, inspect aggregate results and decide if targeted tuning is worth it.
```

Decision rule: if the deliverable file does not exist on disk, the next
action is a full end-to-end run that saves it — not another per-item
tweak.

## Stop condition when no external oracle

When the task gives you noisy inputs (OCR, scraped HTML, parsed PDFs)
and **no accessible oracle** (no held-out labels, no reference parser,
no canonical source), the stop condition cannot be "my pipeline matches
my guesses". Writing a self-authored `expected = {...}` table by
eyeballing the raw inputs and tuning the extractor until it matches
that table silently trains the pipeline to your eyeball labels, not to
reality — the output ships correctly shaped and still gets reward 0.0.

1. **Do not fabricate an oracle.** Do NOT write a hard-coded
   `expected`/`gold`/`truth` dict covering most/all input ids inside
   a debug or test script and use `pipeline_output == expected` as
   the pass/fail stop condition. Inspecting a few inputs for a sanity
   anchor on unambiguous rows is fine; using that inspection as the
   all-rows stop condition for extractor tuning is not.
2. **Use intrinsic signals instead.** The legitimate stop condition
   is a combination of signals that do not depend on your eyeball
   labels: per-field validator pass, cross-field reconciliation
   between sibling values (e.g. `cash − change ≈ total`),
   cross-variant agreement on the SAME numeric value (not just same
   tier), and distributional sanity (values fall in a plausible
   window). Rows that fail any of these are LOW-CONFIDENCE.
3. **Low-confidence rows ship as-is.** Do not tune the extractor to
   bend a low-confidence row toward the value you guessed from the
   raw input — the real oracle gets to discover the disagreement.
   Mode voting and "prefer v0" are tie-breakers, not validators;
   when two OCR variants disagree with equal frequency on the same
   field, flag the row and ship the top-vote value rather than
   iterating until the vote tips your way.

```python
# Generic shape — specifics (intrinsic-signal menu, tie-break protocol,
# forbidden-pattern grep) live in references/no-oracle-self-validation.md
def ready_to_ship(row, siblings, cross_variant_votes, validators):
    checks = [
        all(v(row.get(f)) for f, v in validators.items()),     # validators
        reconciles_with_siblings(row, siblings),               # cross-field
        max_variant_agreement(row, cross_variant_votes) > 1,   # cross-variant
        in_plausible_distribution(row),                        # distribution
    ]
    if all(checks):
        return ("high_confidence", row)
    return ("low_confidence_ship_as_is", row)   # NOT "tune until matches guess"
```

Decision rule: if your workspace contains a self-authored `expected`
dict covering the ambiguous rows and your stop condition is "all rows
match expected", delete the dict and switch to intrinsic signals —
even if that means shipping rows you believe are wrong. Your belief
is correlated with your pipeline (both come from reading the same
raw inputs); the oracle is not.

Read `references/no-oracle-self-validation.md` when the task has no
accessible oracle and you are tempted to construct one from your own
inspection of the raw inputs. Skip when the task provides an external
verifier (schema with semantic rules, a second parser, golden examples
in the problem statement) — those are legitimate stop conditions.

## OCR / scanned-document batch extraction

When batch inputs are images or scanned PDFs that must be OCR'd into
typed fields (dates, amounts, totals), **majority voting over a narrow
OCR sweep is not a correctness mechanism**. When several variants share
the same misread, voting cements the wrong answer. Use validity-aware
scoring instead: a validator predicate per field type is the primary
ranking signal; frequency only breaks ties among valid candidates.

```python
# Generic shape — specifics (PSM set, repair tables, verification loop)
# live in references/ocr-batch-extraction.md
from collections import Counter

def pick_field(candidates, validator):
    freq = Counter(c for c in candidates if c is not None)
    ranked = sorted(freq.items(),
                    key=lambda kv: (validator(kv[0]), kv[1]),
                    reverse=True)
    return ranked[0][0] if ranked else None   # None → row needs re-OCR
```

Decision rule: if any row in the first full pass has a `None` field or
only invalid candidates, re-OCR that row with an augmented pipeline
(additional PSM modes, upscaled preprocessing, digit-confusion repair)
before the final save. Spot-checking a few rows is not verification.

Read `references/ocr-batch-extraction.md` when the input is a batch of
images/scanned PDFs requiring OCR into structured fields. Skip when
inputs already have an extractable text layer (text PDFs, CSV, HTML) —
plain parsing is sufficient.

Read `references/keyword-anchored-field-selection.md` when the field is
picked by scanning the extracted text for a keyword (e.g. "TOTAL",
"AMOUNT DUE", "INVOICE DATE") rather than by fixed position, especially
when a negative keyword list is used to skip tax/subtotal/summary rows.
Do **not** re-implement substring exclusion or first-match-wins within
a tier even if the chapter's code looks longer than yours — those are
the exact failure modes it exists to prevent. Skip when the field has
a fixed position or a single unambiguous regex suffices.

## Common Workflow
1. **Choose tool**: pandas for data, openpyxl for formulas/formatting
2. **Create/Load**: Create new workbook or load existing file
3. **Modify**: Add/edit data, formulas, and formatting
4. **Save**: Write to file. For batch/per-item tasks, this save must
   happen on the first full pass over all inputs, not after tuning
   converges — see "Baseline deliverable before per-item tuning".
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

## Formula Verification Checklist

Quick checks to ensure formulas work correctly:

### Essential Verification
- [ ] **Test 2-3 sample references**: Verify they pull correct values before building full model
- [ ] **Column mapping**: Confirm Excel columns match (e.g., column 64 = BL, not BK)
- [ ] **Row offset**: Remember Excel rows are 1-indexed (DataFrame row 5 = Excel row 6)

### Common Pitfalls
- [ ] **NaN handling**: Check for null values with `pd.notna()`
- [ ] **Far-right columns**: FY data often in columns 50+
- [ ] **Multiple matches**: Search all occurrences, not just first
- [ ] **Division by zero**: Check denominators before using `/` in formulas (#DIV/0!)
- [ ] **Wrong references**: Verify all cell references point to intended cells (#REF!)
- [ ] **Cross-sheet references**: Use correct format (Sheet1!A1) for linking sheets
- [ ] **No deliverable on disk**: On batch/per-item tasks, iteration budget is spent tuning edge cases while the output file was never saved — ship a baseline end-to-end first, then tune.
- [ ] **A degenerate OR self-identified-wrong extraction output is a rule-bug signal, not an answer.** On noisy-input batch extraction (OCR, scraped text, keyword-anchored field pulls), every form of "the output is suspect" means the extraction *rule* is suspect, not the input. This covers (a) `None`/empty-cell outputs; (b) a majority-vote consensus that is still wrong; (c) an implausibly small value next to much larger sibling values on the same record; AND (d) **any row your own reasoning trace has flagged as wrong** — before saving, scan your notes for phrases like `"wrong on X"`, `"X still fails"`, `"a couple of hard cases remain"`, `"X is corrupted"`. Each flagged row requires **one** targeted re-extraction attempt (relax exclusion, add OCR-noise fuzzy aliases, bump upscale from 1.5× to 2–3×, try the next-ranked same-record candidate from `references/keyword-anchored-field-selection.md` §3/§4, apply digit-confusion repair even when the value passes `AMOUNT_RE`) OR an explicit written reason why no fix is reachable within the budget. **Silently shipping a value you have already identified as wrong is forbidden** — this is the hard limit on the "cap effort on any single hard input" rule above. Diagnostic steps: (1) rank variants by validator-pass first, frequency only as tie-break; (2) if a negative-keyword exclusion emptied the candidate set, the exclusion is almost certainly matching descriptors on valid lines — switch to whole-word regex + OCR-noise alias classification (see `references/keyword-anchored-field-selection.md`); (3) run a full-table verification pass that includes cross-field sanity (e.g. `cash − change ≈ total`), not just a spot-check, and switch to the next-ranked same-record candidate before paying for a re-OCR; (4) read 2–3 flagged rows with your own eyes and confirm the rule picks what a human reader picks — **but only when you can cross-check against an external oracle; when YOU are the sole source of ground truth this check is circular and silently selects for self-consistent-but-wrong pipelines, see "Stop condition when no external oracle" above and `references/no-oracle-self-validation.md`.**
- [ ] **No external oracle → do not fabricate one.** If the task provides no held-out labels, no reference parser, and no canonical source, the stop condition cannot be "my pipeline matches a `expected = {...}` dict I typed in by eyeballing the raw inputs". That stop condition trains the pipeline to your guesses, not to reality; the output ships correctly shaped and reward is still 0.0. Legitimate stop conditions are intrinsic signals only — validator pass, cross-field reconciliation, cross-variant agreement on the SAME numeric value, distributional sanity. Ship low-confidence rows as-is rather than tuning until they match a guess. See `references/no-oracle-self-validation.md`.

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
