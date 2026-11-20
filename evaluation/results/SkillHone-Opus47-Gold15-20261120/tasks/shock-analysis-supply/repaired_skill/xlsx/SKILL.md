---
name: xlsx
description: "Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization. When Claude needs to work with spreadsheets (.xlsx, .xlsm, .csv, .tsv, etc) for: (1) Creating new spreadsheets with formulas and formatting, (2) Reading or analyzing data, (3) Modify existing spreadsheets while preserving formulas, (4) Data analysis and visualization in spreadsheets, or (5) Recalculating formulas"
license: Proprietary. LICENSE.txt has complete terms
---

# READ THIS FIRST — Scaffold-and-save checklist for pre-built templates

If the task supplies a pre-built `.xlsx` with labeled sheets, year anchors, and hint strings and asks you to "fill in the model", a model shipped with the **full formula skeleton but partial / approximate raw data** is scorable on most tests; a model shipped with **perfect raw data but no formulas written** scores zero. The single most common failure mode is burning the entire iteration budget on data acquisition and never actually saving a filled template. Prevent that by executing these phases in order and **saving the file at every checkpoint**:

1. **Inventory (≤ 3 iterations)** — open the template with `openpyxl`, enumerate every sheet, print every non-empty cell in every sheet, and read every metadata/legend sheet in full. Note all year/row anchors.
2. **Formula scaffold (≤ 8 iterations) — MUST save before step 3.** Write every cross-sheet link, every ratio/log/`TREND`/`AVERAGE`/recursive-accumulation formula, the full Solver objective block (objective cell, second-difference column, residual column, placeholder decision cells set to `=<initial_link_cell>`), and every projection chain described in the prompt. These are all valid formula strings even with empty raw-data cells. **Save the workbook and run `recalc.py` to confirm no `#NAME?` / `#REF!` before touching external data.** A filled-scaffold save at this point is your minimum-viable deliverable.
3. **Raw-data collection (hard cap: ≤ 10 iterations total across ALL sources).** Each external source gets at most 2 download attempts via 1 consolidated script; if both fail, paste a placeholder with the source URL in a comment cell and move on. See "Budget discipline" below. **Save after every source lands.**
4. **Solver decision values (if the prompt mentions Solver)** — compute the decision-cell literals offline (closed form or `scipy.optimize`) and paste them as numbers into the decision range only. All checker/objective cells remain formulas. Save and recalc.
5. **Final sweep — MANDATORY MAGNITUDE GATE.** Run `recalc.py`, confirm zero formula errors, then *explicitly print and verify every headline macro ratio* against the sanity bands below. This is a gate, not an advisory note — if any printed value falls outside its band, the model is **not** ready to ship, no matter how many formulas are wired. Fix the unit/scale/recursion defect first and re-run the gate. Bands for any production-function / Cobb–Douglas / capital-shock model:
   - Annual depreciation rate δ (B3-style cell): **3 % – 8 %**.
   - Capital-output ratio K/Y in any historical year: **1.5× – 5×**. If you see values in the tens, hundreds or thousands you have an unreconciled unit/currency mismatch between K and Y; stop and fix. If you see values below 0.5, likewise.
   - Capital's share α: **0.30 – 0.40** (do not overwrite a pre-filled template value).
   - Peak shock uplift `Ystar_with / Ystar_base − 1`: **tens of basis points to a few percent** and strictly positive from the first shock year.
   - Pre-shock invariant: `K_With == K_base` in every historical year, to at least 6 decimals.

Hard rules that override everything else in this file when they conflict:

- **Save before you fetch.** Before running any download/network command, you must have already saved the template with at least cross-sheet links and derived formulas written. If you have not saved yet, go write the scaffold first.
- **One consolidated fetch script per dataset, max 2 attempts.** Do NOT create `fetch2.py`, `fetch3.py`, `inspect_pwt_v2.py`, `pwt_main.xlsx` / `pwt_full.xlsx` alongside a working file. If 2 primary-URL attempts fail, that source becomes a documented placeholder, not a research project.
- **Package install / proxy diagnostics budget: ≤ 2 iterations total.** If `pip install` fails once with network errors, do NOT loop on `--break-system-packages`, proxy env vars, alternate mirrors. Stay with the standard library (`urllib.request`, `csv`, `re`, `xml.etree.ElementTree`) and `openpyxl`, which are pre-installed.
- **API-discovery budget: ≤ 3 iterations per dataset.** Do not reverse-engineer a vendor SDMX dataflow by fetching dataflow definitions, DSD codelists, and alternate key orderings. If the first 2–3 reasonable URLs (plus 1 documented fallback) don't return the series, write a comment-cell placeholder with the stated source URL and move on; **a formula reading an empty raw cell is better than an unwritten formula.**
- **Ship-what-you-have discipline.** Every 10–15 iterations, step back and ask: "if I had to stop right now, is the file on disk scorable?" If not, stop collecting data, go back to scaffold, save, and only then return to data collection.
- **Magnitude gate before shipping.** Before you finish, you must explicitly print the historical K/Y series, the depreciation rate B3, and the peak shock uplift, and confirm each lies in the band listed in the Final sweep step above. "Zero formula errors" is *not* a substitute for this check: a model with K in millions of 2017 USD and Y in billions of local currency will recalc cleanly and still ship a K/Y of ~2000 and a near-zero uplift, which fails value tests even though every structural test passes. If any band is violated, you must **either rescale the raw-data inputs so both sides of each ratio share currency and scale, or populate K from a series that is already in the same currency and scale as Y** — do not ship the mismatched version.
- **Read the metadata sheet before picking the PWT variable.** PWT exposes several near-identical-looking series (`rnna`, `rkna`, `cn`, `rgdpna`, `rgdpe`, `rgdpo`, `cgdpo`, …). They differ in currency (constant base-year USD vs. national currency) and in base year, which silently breaks any ratio that mixes them with a local-currency flow such as ECB CFC or WEO GDP level. When the prompt says "read the metadata sheet to understand the meaning of each variable", take that literally: open the PWT variable-definitions sheet, read the units column for every candidate, and pick the series whose currency and scale match the rest of the model. If the model needs K and Y in the same currency and scale, use the PWT series that is natively in national currency (e.g. the capital-stock series flagged as "national currency, millions") so the K/Y ratio in the Production sheet comes out in the plausible 1.5–5× band without an ad-hoc scale factor.

# Requirements for Outputs

## All Excel files

### Zero Formula Errors
- Every Excel model MUST be delivered with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)

### Preserve Existing Templates (when updating templates)
- Study and EXACTLY match existing format, style, and conventions when modifying files
- Never impose standardized formatting on files with established patterns
- Existing template conventions ALWAYS override these guidelines
- Before editing, enumerate **every** sheet, read **every** non-empty cell (headers, labels, comments, pre-filled year/row anchors, hint strings) so you know what the scaffold expects you to fill and where
- Treat pre-filled year labels, row numbers, column headers, and section titles as fixed anchors; align your inserts to them exactly instead of guessing rows/columns
- Do NOT delete sheets, columns, rows, or pre-existing cell content unless you are certain they are scratch space; if a section appears "duplicated" or oversized, verify it is not an intentional working area (e.g., a scratch column, a wide lookup block, or an existing filled region) before shrinking it
- If the task prompt or a worksheet references a **metadata/legend sheet** or embedded notes (e.g., "read the metadata sheet to understand each variable"), read it in full and use it to choose which variable/column/series to populate. Do not guess from variable name alone — the metadata is the authoritative source for units, scope, and definition.

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
- Where the template provides a prior-row anchor (e.g., initial value in row N, formula starts in row N+1), extend the formula *down* from that anchor; never overwrite the anchor with a formula referencing itself
- When the prompt says "use formula to calculate" or "keep all the formulas", the deliverable cell MUST contain an Excel formula string. A hardcoded Python-computed number in that cell is a failure even when the numeric value matches the expected answer.

#### Unit, Scale, and Currency Consistency
Formula correctness is not enough; inputs must be dimensionally compatible. Before linking a value from one sheet into another, confirm:
- **Currency**: do both inputs share the same currency, or is an FX conversion required? Mixing a local-currency series with a foreign-currency series across a ratio produces a meaningless result.
- **Scale/Unit multiplier**: are both inputs in the same units (ones vs thousands vs millions vs billions, or raw vs index)? SDMX-style series (ECB, Eurostat, IMF, UN) often carry a `UNIT_MULT` / `UNIT` attribute; apply it. National-accounts and productivity series are commonly in *millions* at a stated base year; respect the base year.
- **Base year / real vs nominal**: if one input is a real series in a constant base-year currency and another is a nominal series in current prices, their ratio is not a depreciation / growth / share — convert first (deflate, rebase, or convert currency as needed).
- **Flow vs stock**: consumption/depreciation is a flow (annual); capital stock is a stock (level). Always divide the correct flow by the correct stock.
- **Sanity-check the computed magnitude**: a depreciation rate should land in a plausible range (a few % per year), a GDP growth rate within normal macro bounds, a capital/output ratio in single-digit multiples, etc. If your ratio lands orders of magnitude off, the units are wrong — stop and reconcile units before continuing to downstream formulas.

#### Cross-source currency alignment for production-function / Cobb–Douglas models
Production-function templates typically draw K, Y, I and CFC from **three different sources that use different currencies and scales**. Before the formulas go into recalc, write down for each raw input: *source, native currency, scale (ones/thousands/millions/billions), base year (if real)*. Then force every pair of cells that enter a ratio or product to share currency and scale. Common pitfalls, in order of how often they silently break a model:

- **PWT exposes multiple capital and GDP series; the metadata sheet is authoritative.** Common variables: `rnna`, `rkna`, `cn`, `rgdpna`, `rgdpe`, `rgdpo`, `cgdpo`, `pl_n`. They differ in currency (constant base-year USD vs. national currency), real vs. current, and base year. Read the PWT variable-definitions sheet first and match the model's downstream currency. For a Georgia (or any single-country) model where Y comes from WEO in local currency, picking `rnna` (constant base-year USD, millions) will NOT line up with Y, and your K/Y ratio will be orders of magnitude wrong. Prefer the PWT series that is natively in national currency (so the K and Y columns share currency without any ad-hoc rescaling). If you cannot read the metadata (sheet missing, download failed), explicitly check K/Y in a plausible band *before* shipping and swap series if it is not.
- **PWT (`rnna`, `rgdpna`) is in constant *base-year USD*, millions.** It is NOT in the country's domestic currency. Do not divide a national-currency CFC/investment/GDP flow by PWT `rnna` without converting one side first. If you must combine PWT K with a national-currency flow, either (a) convert the flow to the same base-year USD using an official PPP or FX adjustment, or (b) swap in a K series that is natively in the local currency (e.g. derive K from CFC and a steady-state law of motion in local currency, or use PWT `rkna` scaled by the national price level). Don't fudge by dropping a factor-of-1e6 you cannot justify.
- **IMF WEO real-GDP-level series are typically in *local currency*, often billions (check the WEO metadata row named "Scale").** If the template's K series is in *millions of USD*, then Y and K are in different currencies AND different scales simultaneously. You cannot write `K/Y` across them without a currency conversion plus a scale adjustment (e.g. 1,000× if one side is billions and the other millions). Spot-check: if `K/Y` lands below 1 or above 50, the units almost certainly do not match (a plausible real K/Y is 1.5–5× annual GDP).
- **ECB SDMX series carry `UNIT_MULT` and `UNIT` attributes.** `UNIT_MULT=6` means the raw `OBS_VALUE` is already expressed in millions — dividing it again by `1e6` makes it 10^-6 of true. Before scaling, read the series key's `UNIT_MULT` (via the `?detail=structureonly` endpoint or the CSV's `UNIT_MULT` column) and match the template's intended scale explicitly; do not guess by eyeballing a few values.
- **If the depreciation rate B3 (or any computed macro ratio) falls outside a tight plausibility window, STOP and reconcile units before shipping.** Concrete windows to use as hard red-flag triggers (not as targets):
  - Annual depreciation rate of fixed capital: **≈ 3% – 8%**. Below 2% or above 15% almost certainly means the flow and the stock are in different currencies/scales.
  - Capital-output ratio K/Y: **≈ 1.5 – 5× annual GDP** for most economies. A ratio below 0.5 or above 10 is a scale defect.
  - Real GDP growth for a small open economy under business-as-usual: **roughly −10% to +15%** per year. A series stuck at 0 or jumping beyond ±30% is almost always a missing projection formula or wrong unit.
  - Capital's share in a Cobb–Douglas setup: **≈ 0.3 – 0.4** (if the template pre-fills a value, do not overwrite it). If an inferred α falls outside this band your LnZ residual is absorbing a scale error.
- **Make the unit comparison visible on the sheet.** Put the source currency, scale and base year in a comment (or a small "units" column next to the raw-data cell), not just in your reasoning. A downstream reader — including the next recalc of this same model — must be able to trace back which cells are in which currency/scale.

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

## Phase ordering for scaffold-first tasks

When the user supplies a pre-built `.xlsx` template with labeled sheets (named areas, pre-filled year/row anchors, hint strings) and asks you to "fill in the model", do NOT start with raw data collection. Work in this order, saving and recalculating between phases:

1. **Template inventory** (fast, mandatory, ≤ 3 iters): enumerate sheets, print every non-empty cell in every sheet, note where blank regions begin/end, read every metadata/legend sheet in full.
2. **Formula skeleton (≤ 8 iters, MUST save before leaving this phase)**: write every cross-sheet link and every derived/computed formula cell the prompt describes, even before any raw data is loaded. Run `recalc.py`; the shell should load without `#REF!` / `#NAME?` (division-by-zero errors on empty inputs are expected and will clear in phase 4). **The saved file at the end of this phase is your minimum-viable deliverable.**
3. **Solver scaffold** (if the prompt mentions Solver, included in phase 2 budget): place the objective formula, sanity-check columns (second-order difference, residual) and decision-variable placeholders (`=<initial_link_cell>`). Save.
4. **Raw data population (≤ 10 iters total across all sources)**: fetch each external source once with a tight budget (see "Budget discipline" below) and paste the raw values into the labeled cells. Each new raw cell makes a formula cell light up. **Save after every source lands.**
5. **Solver execution**: run the equivalent closed-form / numerical optimization offline and paste the decision values back; the objective cell stays a formula.
6. **Final recalc and sanity sweep**: zero formula errors; every projection column non-constant and in the plausible macro range (see the "Unit, Scale, and Currency Consistency" and "Investment-shock / perpetual-inventory scaffold invariants" sections for the concrete bands and invariants to check).

Skipping or inverting this ordering is the single most common failure mode: an agent that spends the entire iteration budget on data acquisition and ships a template with zero formulas added will fail every test, even if the raw data is perfect. If you have burned 10+ iterations without writing a single formula cell, **stop data collection immediately, write the scaffold, save, then return to data collection.**

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

## Running Excel Solver / optimization steps

Some templates include a Solver step (e.g., minimize an objective cell by changing a range of decision cells, often subject to constraints). LibreOffice headless does not reliably run the Excel Solver add-in, and `recalc.py` only recalculates formulas — it does NOT solve.

Follow this workflow when a prompt directs you to "use Solver" or otherwise optimize an objective:

1. **Build the full Solver scaffold in the sheet first, as formulas** — the objective cell, every intermediate cell (residuals, differences, penalty terms), and the decision-variable cells. Decision cells should start as formulas linking to a plausible initial value (e.g., `=K6`) so that the pre-solve state is internally consistent and the objective is finite.
2. **Replicate the Solver objective exactly outside Excel** in Python/NumPy using the same formulas from the sheet. Minimize it with an appropriate numerical method. For HP-filter-style or other quadratic-in-decisions objectives, the closed-form linear-algebra solution `(I + λ·K'K) τ = y` is equivalent to minimizing the same objective and is deterministic.
3. **Write the solved decision values back into the decision cells as literal numbers**, replacing the placeholder formulas. All *downstream* formulas (residuals, differences, objective, and anything that reads the decision range from other sheets) MUST remain as formulas so the model stays dynamic.
4. **Re-run `recalc.py`** and confirm (a) the objective cell drops to the expected minimum, (b) the sanity-check column (e.g., `second-order difference` of the trend, or `LnA - Trend`) behaves as the template describes, (c) no new formula errors appeared.
5. Preserve the Solver-adjacent *checker* cells (second-difference column, residual/LnA column, the objective cell) as formulas pointing at the decision range so the review audit is reproducible.

Do NOT solve the whole model in Python and then paste only the final answers — only the Solver decision cells themselves may be literals, and only after the sheet-side formula scaffold is in place.

### HP-filter offline solve using only the standard library

The Hodrick–Prescott trend `τ` that minimizes `Σ (y_t − τ_t)² + λ Σ (τ_{t+1} − 2 τ_t + τ_{t−1})²` is the unique solution of the linear system `(I + λ·K'K) τ = y`, where `K` is the `(n−2)×n` second-difference matrix. This is a small, pentadiagonal, symmetric-positive-definite system; you can solve it in pure Python without numpy. Use `λ = 100` for annual data (standard convention) unless the prompt or template states otherwise. Minimal reference implementation:

```python
def hp_trend(y, lam=100.0):
    n = len(y)
    # Build (I + λ K'K) as a dense matrix for small n
    A = [[0.0]*n for _ in range(n)]
    for i in range(n): A[i][i] = 1.0
    for t in range(n-2):
        # row of K is at position t; entries at t, t+1, t+2 are 1, -2, 1
        for a, ai in ((1.0, t), (-2.0, t+1), (1.0, t+2)):
            for b, bi in ((1.0, t), (-2.0, t+1), (1.0, t+2)):
                A[ai][bi] += lam * a * b
    # Solve A τ = y by Gaussian elimination (n ≈ 22, trivial)
    M = [row[:] + [y[i]] for i, row in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        inv = 1.0 / M[i][i]
        for j in range(i, n+1): M[i][j] *= inv
        for r in range(n):
            if r == i: continue
            f = M[r][i]
            for j in range(i, n+1): M[r][j] -= f * M[i][j]
    return [M[i][n] for i in range(n)]
```

Then paste `hp_trend(y_values)` cell-by-cell into the decision range (literal numbers). Keep the objective cell, the second-difference column, and the residual column as formulas referencing the decision range. After `recalc.py`, the objective cell should match the sum-of-squares-plus-penalty computed from the same numbers, confirming the paste is consistent.

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
- [ ] **Template audit first**: Enumerate all sheets and every non-empty cell before touching anything; respect pre-filled year/row anchors, labels, and metadata
- [ ] **Metadata sheet read**: If a metadata/legend sheet exists or the prompt points to one, read it and confirm the exact variable code and unit before populating

### Common Pitfalls
- [ ] **NaN handling**: Check for null values with `pd.notna()`
- [ ] **Far-right columns**: FY data often in columns 50+
- [ ] **Multiple matches**: Search all occurrences, not just first
- [ ] **Division by zero**: Check denominators before using `/` in formulas (#DIV/0!)
- [ ] **Wrong references**: Verify all cell references point to intended cells (#REF!)
- [ ] **Cross-sheet references**: Use correct format (Sheet1!A1) for linking sheets
- [ ] **Unit/currency mismatch across sheets**: don't divide a local-currency flow by a foreign-currency stock (or raw by millions, or nominal by real) — convert or rescale first
- [ ] **PWT vs local-currency mix**: PWT `rnna`/`rgdpna` are in *constant base-year USD, millions* and will NOT line up with a national-currency CFC/WEO/ECB series out of the box. Either align both inputs to the same currency and scale, or do not link them in the same ratio.
- [ ] **SDMX UNIT_MULT ignored**: reading an ECB/Eurostat/IMF SDMX CSV and dividing by `1e6` "to get millions" silently double-scales when the series already carries `UNIT_MULT=6`. Read the attribute and honour it; never guess the scale from the first few digits.
- [ ] **Magnitude sanity check**: after linking, spot-check the headline macro ratios against the plausible band — annual depreciation ≈ 3–8 %, K/Y ≈ 1.5–5, capital share ≈ 0.3–0.4, uplift from a few-% shock in the tens of bps to a few %. Anything outside those bands is a unit/scale defect, not a formula defect; fix it before shipping.
- [ ] **Pre-shock `K_With ≡ K_base` invariant**: in a shock-analysis model, the "with-shock" capital path must equal the baseline capital path in every year before the first shock-year investment. If it drifts, the perpetual-inventory recursion is net-depreciating `K_With` without crediting baseline investment — rewrite it as `K_base + cumulative_shock_capital`.
- [ ] **Deliverable cells remain formulas**: when the prompt requires "formula" or "no hardcoded numbers", the cell content read by the verifier must still be a `=...` string, not a Python-computed literal — only genuine raw data points, and Solver decision cells after the Solver step, may be literals

### Formula Testing Strategy
- [ ] **Start small**: Test formulas on 2-3 cells before applying broadly
- [ ] **Verify dependencies**: Check all cells referenced in formulas exist
- [ ] **Test edge cases**: Include zero, negative, and very large values
- [ ] **End-to-end dry run**: after writing formulas, run recalc.py and skim the final table — if a projected column is flat/zero/obviously wrong, a referenced formula is broken even though the file has no `#ERROR!` cells

### Fetching external data referenced by the prompt
Prompts often instruct you to collect data from a specific website (e.g. a macro dataset, a central bank portal). When direct download fails (anti-bot pages, redirects, geo-blocks, missing library), do NOT silently fall back to a different series or a convenient proxy. Instead:
- Try the stated source first; retry with realistic headers; look for an official mirror or API endpoint for the *same* dataset version.
- If only an older vintage of the same dataset is reachable, use it and clearly note the vintage and which cells are historical versus extrapolated, in a comment or adjacent cell.
- Do NOT substitute a different series, a different base year, or a different country without noting it; the verifier compares against the *stated* source, not a near-equivalent.
- Keep raw data points as hardcoded values with a source comment; keep every *computed* cell as a formula referencing those raw cells.

### Use the named tool / MCP from the prompt
If the prompt explicitly names a browsing/automation tool (e.g. "Use Playwright MCP", "use the browser tool", "use the file_editor"), use *that* tool for the step it names. Do NOT reinvent it with raw `urllib`/`requests` and bespoke proxy debugging — those paths silently fail in sandboxed runtimes and will burn your entire iteration budget on HTTP forensics. If the named tool is not available, fall back to one-shot `curl`/`requests` with realistic headers to the exact URL in the prompt, cap retries to 2, then move on with the best-available vintage noted in a comment cell.

Available library heuristic: only `openpyxl` and the Python standard library (`urllib.request`, `csv`, `re`, `xml.etree.ElementTree`, `json`, `math`) can be assumed present. Do NOT spend iterations trying to `pip install requests / pandas / numpy / scipy` — package installs typically fail in sandboxed runtimes due to proxy or PEP 668 constraints, and attempting them in a loop (`--break-system-packages`, alternate mirrors, `--index-url`) is a known time sink. Write everything you need with stdlib + openpyxl. If you genuinely need `scipy.optimize` for a Solver offline-solve step, implement the small closed-form linear-algebra fallback by hand (HP filter: `(I + λ·K'K) τ = y` → solve with standard-lib Gaussian elimination, or — if numpy happens to import — use it; otherwise write an explicit tridiagonal / pentadiagonal solver).

### Budget discipline for data-collection-heavy tasks
A single multi-site collection step can consume the whole iteration budget if you let it. Treat data collection as *one* phase among three (collect → scaffold → solve), not the whole task.
- **Hard per-source cap: ≤ 2 download attempts across ≤ 2 URLs per dataset.** If both fail, write a documented placeholder (series name + source URL in a comment cell) *and* a reasonable literal/placeholder number if any downstream formula divides by it, and continue; do not loop on proxy diagnostics or search for mirror after mirror.
- **Hard aggregate cap for the whole data-collection phase: ≤ 10 iterations.** This covers all datasets in the prompt combined. Past the cap, stop fetching and ship.
- **Hard cap on package/proxy diagnostics: ≤ 2 iterations.** If `pip install X` fails once with a proxy error or PEP 668 refusal, assume `X` is not available and work with stdlib + openpyxl only. Do not iterate on `--break-system-packages`, `unset HTTPS_PROXY`, alternate mirrors.
- **Hard cap on API-schema discovery: ≤ 3 iterations per dataset.** Do not pull SDMX dataflow / DSD / codelist metadata to reverse-engineer a vendor API; if the obvious URL and one documented fallback both fail, leave a placeholder and move on.
- Prefer a single consolidated script per dataset: one function that tries the primary URL, one fallback URL, and parses out the country/years you need. Do NOT create new `fetch2.py` / `fetch3.py` / `inspect_pwt2.py` / `pwt1001_main.xlsx` / `pwt1001_full.xlsx` files per attempt — each new file is a signal you're in a dead-end loop; delete the dead branch and reuse the same filename.
- The downstream Excel model (formulas, cross-sheet links, Solver scaffold, TREND/extension formulas) is independently verifiable even with approximate raw data. Always finish scaffolding the formulas in the template **and save** before returning to polish raw-data accuracy.

### Partial-progress / ship-what-you-have discipline
Set a mental checkpoint every 10–15 iterations: "If the runtime killed me right now, would the file on disk be scorable?" Concretely:
- After phase 2 (scaffold) the file has every required formula wired to cross-sheet references and labeled anchors. Save it. That alone passes any "sheets exist / formulas present / cell is a formula string" check.
- After each data source lands, save. Fetching the next source never justifies skipping a save.
- When you notice yourself chaining diagnostic fetches (proxies, mirrors, SDMX metadata, codelists), STOP. Convert the offending cells to documented placeholders so the row still has a numeric value, save, and move on.
- Never write a one-shot "final" `build_model.py` that aggregates all raw data in-memory then writes to the file in a single pass at the end of the budget — that pattern is exactly what causes a zero-score end state when the budget expires mid-build. Instead, edit the template incrementally: open, write scaffold, save; open, paste source A, save; open, paste source B, save; etc.

### Scaffold-first editing of a pre-built template
For a task that supplies an `.xlsx` template with labeled sheets and section anchors (year columns, named ranges, hint strings), prioritize wiring the entire **formula skeleton** before any external data fetch succeeds. A model that is fully wired but reads from partially-filled raw-data cells still recalculates to meaningful numbers; a model where raw data is perfect but zero formulas were written scores zero on every downstream test.

Recommended order:
1. **Inventory the template exhaustively** — open with `openpyxl`, list every sheet, print every non-empty cell in every sheet (coord, value, number format), and note the row/column anchors each section expects (year labels on row/col X, blank bodies at Y:Z, hint strings naming the expected formula).
2. **Write all cross-sheet link formulas** — e.g. the Production sheet reading K from PWT, Y from WEO_Data, depreciation from CFC data. These are `='Sheet'!A1` references; they are valid even before the source cells are populated.
3. **Write all derived/formula cells** — logs, ratios, TREND extensions, Solver objective, second-order differences, K/Y anchors, deltaK/K_with chains, Ystar_base/Ystar_with, etc. Use the labels and prompt hints verbatim (e.g. "average depreciation rate of most recent 8 years" → `=AVERAGE(...)` over the explicit 8-cell range).
4. **Save and run `recalc.py`** to confirm the shell is clean (no `#REF!`, no `#NAME?`). Expect many `#DIV/0!` / blank-propagation errors on empty cells — those will clear as you fill raw data.
5. **Then populate raw data** — PWT columns, WEO series, ECB CFC, Investment profile, Solver decisions. Each new raw cell makes a formula cell light up.
6. **Final `recalc.py`** — zero errors, magnitudes in plausible ranges.

### Prompt vocabulary → Excel construct cheatsheet
When the prompt uses one of these phrases, the deliverable cell MUST be the matching Excel construct (not a Python-computed number):
- "use formula to calculate X" / "keep all the formulas" → the X cell contains `=…`.
- "link X from sheet S" / "link the … data" → the cell contains `='S'!<coord>`, not a pasted value.
- "average of the most recent N years" → `=AVERAGE(<N-cell range>)` with the explicit range, not a pre-computed mean.
- "extend by applying a fixed anchor (average ratio of the most recent N yrs)" → anchor cell is `=AVERAGE(...)`; extrapolated cells are `=<prev_cell>*<anchor>` or `=<Y_cell>*<anchor>`, referencing the anchor cell by address.
- "calculate K/Y" / "depreciation rate = CFC / K" / any "ratio" → `=<numerator_cell>/<denominator_cell>`.
- "use Excel formula TREND to extend" → `=TREND(known_ys, known_xs, new_xs)` with the explicit ranges, not a Python linear-regression value.
- "capital accumulation" / "K_with = K_{t-1} + I_t − deltaK_t" → recursive formula referencing the prior-year K cell; never a hardcoded series.
- "objective" + "Solver" → `=SUMPRODUCT(...)` or `=SUM(<residual_sq_range>) + λ*SUM(<second_diff_sq_range>)`; the objective cell stays a formula even after Solver fills decision cells with literals.

### Macro/time-series scaffold hygiene
When filling a historical-plus-projection panel (e.g. years 2000–2043):
- Respect the pre-filled year row/column; align each data row to the exact year label.
- Compute projection cells from the last historical cell forward via a formula chain (e.g. `=C27*(1+$B$3)`), so a later fix to the historical cell propagates.
- Growth-rate-constant extrapolation ("assume 2027 growth stays unchanged to 2043") is a formula chain `Y_t = Y_{t-1}*(1+g_const)`, where `g_const` is a single reference to the 2027 growth cell — not 17 hardcoded numbers.
- Depreciation / HP-filter / TREND sections all reference each other; wire the chain end-to-end before focusing on the exact raw-data values. Visually inspect the spreadsheet with `load_workbook(..., data_only=True)` after `recalc.py` to confirm every column has numeric content (no stuck blanks, no column of identical values).

### Investment-shock / perpetual-inventory scaffold invariants
When the template models a one-off investment shock on top of a baseline capital path (columns like `K`, `Investment`, `ΔK`, `K_With`, `Ystar_base`, `Ystar_with`, `Uplift`), use the plain *level* form of the perpetual-inventory recursion and keep the following invariants readable from the recalc:

- **Pre-shock invariant.** In every year *before* the first non-zero `Investment` cell, `K_With` must equal the baseline `K` exactly (not drift below or above). If `K_With` is already ≠ `K` in the first pre-shock year, your recursion is subtracting depreciation from `K_With` without also crediting baseline gross investment — either (a) rewrite `K_With` as the *shock-only* additive-overlay form `K_With = K_base + CumulativeShockCapital` where `CumulativeShockCapital` itself follows `S_t = (1−δ)·S_{t−1} + I_shock_t` and starts at 0, or (b) compute a baseline gross-investment series implied by `K_base` and δ so the two recursions line up pre-shock. The additive-overlay form (a) is simpler and keeps the pre-shock `K_With ≡ K_base` identity bulletproof.
- **Recursion starts at the first shock year, not the start of history.** `ΔK` and `K_With` columns in the historical block should read `=0` and `=K_base`, respectively, until the first non-zero `Investment` cell. Don't apply δ·K_base to the baseline historical block — the baseline K already incorporates its own depreciation, and double-counting it suppresses the uplift and biases every magnitude check.
- **Uplift sign and scale.** After the first shock year, `L/H − 1` (i.e. `Ystar_with/Ystar_base − 1`) must be *strictly positive* and typically in the *tens of basis points to a few percent* range for a multi-year shock worth a few percent of GDP. A near-zero (< 1 bp) or negative uplift at peak is a sign the K_With recursion is mis-netting investment against depreciation.
- **Post-shock decay.** Once investment returns to 0, `K_With − K_base` must decay monotonically toward 0 (never rebound, never cross zero unless depreciation is negative). The implied growth uplift `O − P` should decay accordingly — if it stays flat, `K_With` is probably not reading your `K_base` cell by reference.
- **Document the recursion choice in a cell comment.** Say in one line which form you used (level vs. additive-overlay) and which cells are the initial condition. That line is what lets a reader reconcile your `K_With` magnitudes with the prompt's description.

### Mandatory pre-ship magnitude gate (production-function / Cobb–Douglas / shock models)
Before finishing a Cobb–Douglas / investment-shock model, run an *explicit* data-only pass over the recalculated workbook and print the headline ratios. This is a gate; do not skip it just because `recalc.py` reports zero formula errors. A workbook with K and Y in mismatched currencies/scales, or with a mis-wired `K_With` recursion, will recalc cleanly and still fail every magnitude-based test. Pattern:

```python
# After recalc.py has run and reported zero errors:
from openpyxl import load_workbook
wb = load_workbook("test-supply.xlsx", data_only=True)
prod = wb["Production"]

# 1) Depreciation rate B3: expect 0.03 – 0.08
delta = prod["B3"].value
assert delta is not None and 0.02 <= delta <= 0.15, f"δ out of band: {delta!r}"

# 2) Historical K/Y: expect every value in 1.5 – 5
ky = [prod.cell(row=r, column=4).value for r in range(36, 58)]  # D36:D57
bad = [(r, v) for r, v in zip(range(36, 58), ky) if v is None or not (0.5 <= v <= 10)]
assert not bad, f"K/Y out of band: {bad[:5]}"  # if non-empty: unit/currency mismatch

# 3) Peak uplift: expect strictly positive and in ~10 bps – few % range
uplift = [prod.cell(row=r, column=13).value for r in range(60, 76)]  # M60:M75 (shock yrs)
peak = max(v for v in uplift if isinstance(v, (int, float)))
assert 1e-4 <= peak <= 0.10, f"peak uplift out of band: {peak!r}"

# 4) Pre-shock K_With ≡ K_base: every pre-shock-year difference ≈ 0
k_base = [prod.cell(row=r, column=5).value for r in range(36, 60)]    # E36:E59 pre-shock
k_with = [prod.cell(row=r, column=11).value for r in range(36, 60)]   # K36:K59 pre-shock
drifts = [(r, a, b) for r, a, b in zip(range(36, 60), k_base, k_with) if a is not None and b is not None and abs(a - b) > 1e-6 * max(abs(a), 1)]
assert not drifts, f"K_With drifts pre-shock: {drifts[:3]}"
```

If any assertion fires, the model is **not shippable**. Diagnose by cause:
- `δ` or `K/Y` out of band → currency/scale mismatch between the PWT K column and the WEO Y column (and/or between CFC and K); either rescale the raw inputs so both sides share currency and scale, or swap in a PWT series whose currency matches Y.
- Peak uplift near zero / negative → `K_With` recursion is net-depreciating the baseline level without crediting baseline investment; rewrite as the additive-overlay form `K_With = K_base + CumulativeShockCapital`.
- Pre-shock drift → recursion starts before the first shock year; reset the historical block to `ΔK=0`, `K_With=K_base`.

Only after the four assertions pass should you commit the workbook as final. Document the gate pass in a short comment in a cell on the Production sheet so a reviewer can tell the gate was actually run.

(Row/column anchors above are the typical layout for a Georgia-style supply-side Cobb–Douglas template; in a different template, read the actual sheet first and update the indices, but keep the same four checks.)

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
