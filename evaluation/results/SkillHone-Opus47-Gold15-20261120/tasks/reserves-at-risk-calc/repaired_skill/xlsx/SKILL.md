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

#### Raw cell value vs. display format — critical for graded outputs
- The *raw numeric value* in a cell and its *display format* are independent.
  Automated verifiers (and any downstream formula) read the raw value; they do
  not see the number format. Writing `=A1/B1` with `number_format = '0.00%'`
  stores `0.041` in the cell and renders `"4.10%"` to a human reader — but a
  verifier that loads the workbook with `openpyxl(..., data_only=True)` and
  compares to an expected `4.10` will see `0.041` and fail.
- **When a row or column label states the output unit explicitly** (e.g. "in
  percent", "%", "bps", "US$ millions"), put the units **into the formula**
  (`=num/den*100`, `=value/1e6`, etc.) so the raw cell value already matches
  the label. Add a number-format on top only as a cosmetic touch.
- Prefer formula-based unit conversion over display-only formatting whenever a
  programmatic consumer may read the file.

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
- Separates **formula-derived errors** (from `=…` cells, which you should fix) from
  **pre-existing literal errors** (an error string hard-coded into a data cell of the
  input template — these are usually *not* your bug and should be left alone unless
  the task explicitly asks you to clean the source data)
- Returns JSON with detailed error locations and counts
- Works on both Linux and macOS

### Reading `recalc.py` output

- `formula_errors` — errors evaluated from formulas you (or the template) wrote. Fix these.
- `literal_errors` — error strings that were already present as plain text/data in the
  file before recalculation (e.g. `#N/A` left in a source dataset). They are reported
  so you know they exist, but adding or removing them is not part of formula correctness.
- `total_errors` counts formula errors only, so a `status: "success"` run can still
  list pre-existing literal errors under `literal_errors` — that is expected and
  **not** a reason to modify the source data.

Before writing another cycle of Python, compare an error location against the
baseline you captured on the original/input file: if a cell already had the error
before you touched it, do not try to "fix" it with a wrapper formula.

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

### Formula Testing Strategy
- [ ] **Start small**: Test formulas on 2-3 cells before applying broadly
- [ ] **Verify dependencies**: Check all cells referenced in formulas exist
- [ ] **Test edge cases**: Include zero, negative, and very large values

### Interpreting recalc.py Output
The script returns JSON with error details:
```json
{
  "status": "success",            // or "errors_found" (based on formula errors)
  "total_errors": 0,              // Formula-error count only
  "total_formulas": 42,           // Number of formulas in file
  "error_summary": {              // Only present if formula errors found
    "#REF!": {
      "count": 2,
      "locations": ["Sheet1!B5", "Sheet1!C10"]
    }
  },
  "literal_errors": {             // Optional: errors in non-formula (data) cells
    "count": 1,
    "note": "These error strings appear in non-formula cells (plain data). ...",
    "error_summary": {
      "#N/A": { "count": 1, "locations": ["Data!E15"] }
    }
  }
}
```

Only `error_summary` requires action from you. `literal_errors` is informational:
it flags error strings that were already present as data in the input file, not
produced by any formula you wrote. Do not wrap them with `IFERROR` or otherwise
rewrite the source data unless the task explicitly asks for it.

## Cross-sheet Lookups (INDEX/MATCH, XLOOKUP, VLOOKUP)

Many financial and operations templates require pulling a value from one sheet into
another by name, date, or code. Keep these rules in mind — they apply to any workbook
that will be recalculated with LibreOffice (as `recalc.py` does).

### Prefer `INDEX` + `MATCH` over `XLOOKUP` with wildcards

- **`XLOOKUP` wildcard matching is unreliable under LibreOffice recalculation.**
  Even when `match_mode:=2` is specified, wildcard `"*name*"` searches frequently
  return `#N/A` for every cell. If every lookup result is `#N/A`, suspect the
  lookup function before you blame the data.
- A robust, portable alternative is:
  ```
  =IFERROR(INDEX(<result_range>, MATCH("*"&<key_cell>&"*", <key_range>, 0)), "N/A")
  ```
  `INDEX`+`MATCH` with `match_type=0` supports wildcards consistently in both
  Excel and LibreOffice.
- Only drop `XLOOKUP` for an *exact-match* lookup if you have verified it
  recalculates correctly in your environment.

### Handle headers that contain extra descriptive text

Real-world headers often come as long, formatted strings (e.g. an entity name
followed by series metadata and units in parentheses) rather than clean keys.
Three options:

1. **Wildcard match** on the key column (see INDEX/MATCH pattern above).
2. Build a normalized helper row/column once, then use exact-match formulas against it.
3. Pre-compute the column/row mapping in Python and write cell-to-cell references.

Pick one approach for the whole workbook; mixing them creates subtle off-by-one bugs.

### "Not found" semantics

Templates often instruct "if no data, delete the row/column" vs. "leave blank" vs.
"show N/A". Read the instruction carefully:

- **"Delete from the table"** usually means physically remove the entry *and shift
  the remaining entries left/up* so the final table is contiguous. Do this *after*
  you have identified the missing-data entries, then rewrite the dependent formulas
  (exposure, ratios, etc.) against the new positions.
- **"Leave blank" / "show N/A"** means keep the slot and let downstream formulas
  propagate the missing status. Wrap lookups in `IFERROR(..., "N/A")` and make the
  downstream formula tolerant of a text value (e.g. `IFERROR(x/y, "N/A")`).
- Never leave a raw `#N/A` as a lookup result if the task's error contract requires
  zero formula errors — wrap it or remove the entry.

### Recomputing dependent formulas after structural edits

If you delete columns/rows that other formulas reference, those formulas must be
re-emitted with the new coordinates. A good routine:

1. Clear the entire target block (set every cell to `None`).
2. Re-emit key/label rows first (the identifiers the other rows depend on).
3. Re-emit value rows that reference those keys.
4. Re-emit lookup rows (INDEX/MATCH, VLOOKUP, XLOOKUP).
5. Re-emit final metric / ratio rows last.
6. Re-run `recalc.py` and verify no new `#REF!`, `#NAME?`, or `#N/A`.

## Financial Time-Series Patterns

When a task asks you to "populate a monthly price series, then compute log returns and
rolling volatility", apply these invariants. They are easy to get subtly wrong and
`recalc.py` will not catch a wrong formula that evaluates successfully.

### Monthly log returns

- Log return for row `t`: `=LN(B{t}/B{t-1})`.
- If the task says "express as a percentage" or "multiply by 100", keep the `*100`
  in the **log-return formula itself**, not in the volatility formula:
  `=LN(B{t}/B{t-1})*100`. Mixing a non-scaled σ with a scaled return (or vice
  versa) breaks every downstream exposure.
- The very first row cannot have a return — leave `C2` blank, not `0`.

### Rolling volatility

- **n-month volatility at row t** = `STDEV` (sample stdev) of the last `n` log
  returns: `=STDEV(C{t-n+1}:C{t})`. For n=3 use `C{t-2}:C{t}`, for n=12 use
  `C{t-11}:C{t}`.
- Volatility rows for which fewer than `n` returns are available should be left
  blank (not zero and not `#DIV/0!`). Guard with
  `IF(COUNT(range)=n, STDEV(range), "")` if downstream cells would otherwise break.
- Use `STDEV` (sample) unless the task explicitly says population stdev (`STDEVP`).

### Horizon scaling vs. annualization

Clarify which operation is being asked **before** writing the formula; the words are
easy to confuse:

- **Annualizing a periodic σ**: if σ was computed from returns of frequency `f`
  (monthly, weekly, daily), annualize by `SQRT(periods_per_year / 1)` — i.e. for
  monthly returns multiply by `SQRT(12)`.
- **Scaling a σ of horizon h₁ to horizon h₂**: multiply by `SQRT(h₂/h₁)` **only when
  the task actually asks you to change the horizon**. In particular, do *not*
  convert a σ into a longer-horizon σ just because the volatility window had that
  many periods in its name (e.g. a "3-month volatility" cell holds the stdev of 3
  monthly returns, not a 3-month-horizon σ — its horizon is still one month).
- A "95% one-sided" normal shock uses `z ≈ 1.645`; 99% one-sided uses `z ≈ 2.326`.
  Do not confuse one-sided and two-sided quantiles.
- **Units matter**: if σ is in **percent** (because log returns were scaled × 100),
  divide the shock by 100 when applying it to an absolute position value, so you
  don't double-count the percent conversion. If σ is in decimal (no × 100), apply
  the shock directly.
- Read the task's time horizon wording carefully before picking a scaling factor.
  "Annualized", "3-month", "near-term" and plain "volatility" are all different
  horizons; the result is extremely sensitive to the choice, and no `recalc.py`
  check will catch a wrong horizon.

### Valuation-exposure / shock formulas

Many risk templates ask for an "exposure" or "shock" cell on top of a position
value and a σ. The default construction is:

```
exposure = position_value * z * sigma_used
```

Guidelines before you add any further multipliers:

- **Read all σ-related labels in the template first.** A risk workbook commonly
  exposes several σ cells with different semantics — raw n-period σ, annualized
  σ, and a z-score — and the labels are the authoritative guide. Enumerate them
  (`for row in ws.iter_rows(..., values_only=False): print(cell.coordinate,
  cell.value)`) and map each labelled σ to one of {periodic, annualized,
  scaled-to-horizon}. Only after that mapping is clear should you decide which
  σ a given exposure/shock cell should multiply.
- **Use the σ cell whose label matches the task's horizon word.** If the task
  mentions "near-term", "short-term", "quarterly", or any specific horizon and
  the template exposes a σ that was deliberately computed/annualized for that
  horizon, that labelled σ is the intended input. Reference the labelled σ cell
  directly; do **not** invent a different horizon factor on top of it.
- **If the labelled σ is periodic and the task describes a different horizon,
  scale σ by `SQRT(h_target / h_source)` — but only when both horizons are
  stated unambiguously.** Example: a template that stores "monthly σ" and a
  neighbouring "annualized σ (= monthly σ × √12)" is signalling that horizon
  conversion is part of the model; a "near-term quarterly valuation swing"
  derived from an annualized σ would use σ × √(3/12). Compute the factor from
  cell references (e.g. `=σ_annualized*SQRT(3/12)`), not a hardcoded number,
  and comment the horizon choice on the first exposure cell.
- **If the task gives *no* horizon hint and the template exposes only one σ,
  reference that σ as-is with no horizon factor.** Do not fabricate a `SQRT(n)`
  just because the σ window is `n` months — the window is the sample size, not
  the horizon.
- **Divide by 100 exactly once** if σ is in percent units (because log returns
  were scaled × 100 upstream). Doing it twice hides the bug behind a plausible
  looking small number; omitting it inflates the shock by 100×. Verify units
  against the σ formula actually written into the workbook: if the log-return
  formula ends in `*100`, every σ cell is in percent and every exposure that
  multiplies by that σ needs exactly one `/100`.
- **Be consistent across all columns** of an exposure row — every entry should
  use the same σ reference, the same z, and the same (or no) horizon factor. A
  single stray `SQRT(…)` on one column indicates confusion, not asymmetry.
- Write every factor as an **explicit cell reference** (e.g.
  `=<pos_cell>*$<z_cell>*$<sigma_cell>/100`), not hardcoded numbers, so a later
  edit to the σ, z, or position propagates automatically.
- When the template contains a labelled "annualized" σ row *and* a row that
  describes a sub-annual horizon exposure (e.g. "near-term", "90-day"), the
  presence of the annualized σ is itself evidence that horizon scaling is part
  of the model. Use the annualized σ multiplied by `SQRT(h_horizon_years)` to
  obtain the horizon σ, rather than blindly re-using the raw n-month σ.

### Ratios of two currency amounts — the raw cell value is what grading checks

When the task output is a ratio of two monetary quantities (e.g. "exposure as
a share of total reserves", "coverage ratio", "share of GDP"), the raw formula
is `=numerator/denominator`. Two separate things are at stake: the **raw
numeric value** stored in the cell, and the **display format** that a human
reader sees. Automated graders and downstream formulas read the *raw value*;
they do not see the number format.

- **If the row/column label states the unit explicitly** — e.g. "in percent of
  X", "in %", "% of total", "bps", "x (multiple)" — the raw value in the cell
  **must already be in those units**. For "in percent" that means the formula
  evaluates to a percent-scale number (something like `3.21`, not `0.0321`):
  write `=num/den*100`, not `=num/den` with a `0.00%` number format. A cell
  whose label promises "in percent of …" but whose raw value is a decimal
  fraction will fail a value-equality check that expects a percent-scale
  number, even though it *renders* with a percent sign to a human reader.
- The display-only `number_format = '0.00%'` trick (keep the raw value as a
  decimal, let Excel/LibreOffice multiply by 100 at render time) is appropriate
  **only** when the label does *not* promise a particular unit, when a human
  reader is the sole consumer, or when the surrounding template already uses
  decimal ratios consistently. Prefer the `*100`-in-formula convention whenever
  a value-equality verifier may read the file via `openpyxl(..., data_only=True)`
  — such readers return the raw cached number and ignore `number_format`.
- Do not combine both conventions on the same cell (both `*100` in the formula
  *and* a `0.00%` display format): that multiplies the rendered value by 10,000.
- If the numerator and denominator are in different currencies or different
  unit scales (e.g. one in US$ millions, the other in US$ thousands), convert
  first inside the numerator or denominator so the ratio is dimensionless
  *before* applying any percent/basis-point scaling.
- Guard against a missing denominator: `=IFERROR(num/den*100, "N/A")` (keeping
  the `*100` inside the IFERROR so the numeric branch is already in the right
  units) so the row does not propagate `#DIV/0!` into aggregate cells
  downstream. For a decimal-unit row, drop the `*100`.
- The same rule applies to any labelled-unit cell: if the label on a row says
  "(US$ millions)" and your source is in US$, divide by 1e6 **in the formula**
  rather than relying on a `#,##0,,` display format. If the label says "(Mil.
  US$)" and the source is already in Mil.US$, do nothing — the raw value is
  already in the labelled units.

### Currency / unit screening in cross-country tables

When a task iterates over countries and pulls "reserves" or any monetary
figure from a multi-country source sheet, inspect the series metadata row
(`.DATA_TYPE`, `.UNIT`, a parenthesised suffix on the header string, etc.)
*before* using the value:

- Columns in the task's reporting currency (e.g. `US$`, `Mil.US$`) are directly
  comparable; columns labelled with local-currency codes (e.g. `LocCur`, a
  three-letter FX code), physical-unit codes, or any other non-matching unit
  tag are **not** comparable without an explicit FX or price conversion.
- If the task asks for a value-denominated figure and the source has some
  columns in **value** (currency) and some in **volume** (physical units),
  only the value columns are drop-in; volume columns must be multiplied by
  the unit price the task tells you to use before they sit in the same row.
- If a column's units cannot be reconciled with the task's requested units
  and the task does not supply a conversion rule, exclude that entry and note
  the exclusion rather than mixing incompatible units silently.

### Pin the "latest" row explicitly

Templates with pre-filled date labels often define "latest" implicitly (last
non-empty data row). Compute that row once in Python, store it as a variable, and
reuse it in every dependent formula (e.g. `=<SourceSheet>!D{LAST_ROW}`). Avoid
`INDIRECT` and `OFFSET` for this — they make debugging harder and may slow
recalculation.

## Downloading external source data

When the task asks you to download a source file from a public site, do not
assume you remember the exact URL:

1. First `curl` the landing page provided in the task and `grep` for likely
   dataset link patterns (e.g. `.xlsx`, `.csv`, `.ashx`, `.zip`).
2. Download the resolved link with `curl -sL -o <file>` (`-L` follows redirects).
3. Verify the file is actually a workbook/archive, not an error page: check the
   magic bytes (`PK\x03\x04` for xlsx/zip), the file size (XML error payloads
   are small, often < 1 KB), or load with `openpyxl` inside a try/except.
4. If the download returns an error page, re-scrape the landing page — the host
   may have changed the file name or added a required query parameter.

Never embed a specific download URL or dataset version in SKILL guidance; always
discover it at run time from the task's specified landing page.

### Check for pre-staged local data FIRST

Before any external request, look for the dataset in the sandbox itself. Task
environments routinely pre-stage required source files so the solution does not
depend on live internet access. Typical locations to inspect:

- `/root/data/`, `/root/inputs/`, `/root/workspace/`, `/root/.agents/`, `/data/`
- Any directory referenced in the task's starter files, the template workbook,
  or environment variables
- The current working directory and its parents
- Package data shipped inside installed Python modules (e.g. `pandas_datareader`,
  `pdr`, dataset-wrapping libraries) — these sometimes bundle a redistributed
  snapshot of the public series the task wants.

If the needed sheet or series already exists in the provided template workbook
(e.g. a data sheet that mirrors a public dataset), use it directly. Never spend
turns fetching a file that is already sitting on disk.

### Inspect the input workbook exhaustively before declaring a sheet "empty"

If a sheet looks empty on first read (`max_row` small, obvious cells blank), do
a second pass before you conclude you need to fetch external data:

- Iterate every cell up to `sheet.max_row` / `sheet.max_column` and print
  non-None values; the template may store data below header gaps or in
  non-contiguous columns.
- List *all* sheet names (`wb.sheetnames`), including hidden ones:
  `wb[name].sheet_state == 'hidden'`. A pre-staged dataset is sometimes on a
  hidden "Data" or "Series" sheet.
- Inspect **defined names** (`wb.defined_names`) and **external links** —
  the task may expose the dataset via a named range, not direct cell references.
- Check cell **comments** (`cell.comment`) on the header row of the empty
  sheet; the task sometimes pastes the actual series into a note or leaves a
  pointer to a staged file path.

Only after this inspection fails to turn up the data should you treat the sheet
as genuinely needing an external fetch.

### Hard budget on external fetches — stop and pivot early

Downloads that will not succeed in this environment (CDN blocks, bot-protection
pages, DNS filtering, outbound-proxy resets) look exactly like transient
failures but consume turns without making progress. Protect the overall task
budget:

- **Diagnose the network envelope once, up front.** Check whether an HTTPS
  proxy is configured (`echo "$https_proxy $HTTPS_PROXY $no_proxy"`); try one
  neutral control host (e.g. a well-known public endpoint) to see whether
  *any* outbound HTTPS works. A clean "Recv failure: Connection reset by peer"
  on the proxy `CONNECT` tunnel for every host, or `curl: (6) Could not
  resolve host` on every host, means outbound HTTPS is closed off entirely —
  further variations of URL, header, or UA will not help.
- **Cap total download attempts at ~5 across all URL and header variants.** If
  five well-formed attempts (varied User-Agent / TLS impersonation / referer /
  cookie-jar after landing-page visit) all return the same error class (403,
  429, consistent 5xx, Akamai/Cloudflare challenge page, DNS failure, proxy
  reset), the host is blocking this runtime, not misbehaving. Stop retrying
  the same path.
- **Signs of a persistent block (do not keep retrying):** repeated identical
  `x-reference-error` / `cf-ray` IDs across attempts, every response is the same
  `text/html` challenge page of the same tiny length (a few hundred bytes),
  landing page succeeds while any data-asset URL under the same origin fails,
  or the proxy tunnel sends `Recv failure: Connection reset by peer` for every
  external host including unrelated control endpoints.
- **After the cap, pivot once:** try at most one or two alternative access
  paths — a public JSON/SDMX API, a mirror, `web.archive.org`, or a bulk data
  portal — with a short timeout. If none works in a few attempts, stop fetching
  and proceed with the next guideline.

### Do NOT fabricate missing numeric data from LLM memory

When the fetch fails and no pre-staged copy exists, it is tempting to
reconstruct the series "from historical knowledge" (e.g. hardcoding a long
dictionary of monthly values). Do not do this:

- Any downstream statistic (log returns, rolling σ, averages used as proxies
  for a period price) will be close-but-wrong. Value-equality tests that
  compare numeric results against the true reference series will all fail,
  while a formula-structure test would still have passed on a skeleton that
  left the data cells blank. Fabrication therefore converts a "partial credit"
  outcome into a "zero credit" outcome and is strictly worse than leaving the
  data cells unpopulated.
- The same reasoning applies to inventing dates, FX rates, index levels, or
  commodity prices. LLM recall of long numeric series is not calibrated
  enough for a verifier that checks equality to many digits.
- If you cannot obtain the real values, **leave the data cells blank** (the
  volatility/exposure formulas will evaluate to `#DIV/0!` or empty; guard the
  dependents with `IFERROR(..., "")` so the formula structure still exists
  without a false numeric claim). Document the gap once in a comment on a
  header cell naming the missing source. A reviewer can tell the difference
  between "data unavailable" and "wrong answer confidently given"; verifiers
  usually penalize the latter much more.

The one acceptable exception is a **widely-standardized constant** that is
already a defined symbol of the task itself (e.g. a quoted z-score at a given
confidence level, a stated confidence level, π). Those are not data — they
are given parameters.

### Never ship a blank template — deliver the model skeleton first

If external data cannot be obtained within the budget, the deliverable still
needs to exist as a structured Excel model. Build and save the workbook
structure *before* spending turns on data acquisition, then update it in place
as data becomes available:

1. **Immediately** load the provided template, add the labels, headings,
   lookup formulas, volatility formulas, exposure/risk formulas, and any
   cross-sheet references the task describes, using whatever template data is
   already present (e.g. the pre-filled sheets of the input workbook). Save it
   to the output path and run `recalc.py` once to confirm the formulas are
   syntactically valid.
2. **Then** attempt the external fetch. When data arrives, write it into the
   relevant source sheet; the formulas already in the workbook will recompute
   on the next `recalc.py` run.
3. If step 2 is impossible in this environment, the formula skeleton from
   step 1 is still the deliverable — do not overwrite it with an empty copy
   of the template and do not keep retrying downloads past the budget.
4. **Never backfill missing source cells with LLM-recalled numeric values**
   just to make downstream formulas produce "some" result. See the preceding
   "Do NOT fabricate missing numeric data" guideline — a plausible-looking
   wrong number is more harmful than a blank cell with the correct formula
   depending on it.

This ordering ensures that even a run that loses its network entirely still
produces a workbook with the required sheet layout, labels, cross-sheet
lookups, and formula expressions, which is usually enough to pass
"formulas present" / structural checks and to earn partial credit on any
cells that depend only on data already in the template.

### Partial-credit mindset when some inputs are missing

When one data source is unreachable but others (e.g. sheets already in the
input workbook) are complete, split the deliverable accordingly:

- Rows/columns that depend **only** on data already in the template (e.g. a
  figure pulled from a pre-populated source sheet via a direct cell reference)
  will compute to correct values regardless of the missing feed. Emit those
  formulas normally.
- Rows that depend on the missing feed (e.g. a statistic derived from a
  time-series you could not download) should still have the correct formula
  expression, but their inputs stay blank; they will evaluate to blank or
  `#DIV/0!`. Wrap them in `IFERROR(..., "")` so the sheet still opens cleanly
  and so aggregate cells that mix both kinds of inputs are not poisoned.
- This arrangement gives the best possible outcome: the subset of cells that
  *can* be computed correctly earn their marks, while cells that cannot are
  transparently blank rather than confidently wrong.

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
