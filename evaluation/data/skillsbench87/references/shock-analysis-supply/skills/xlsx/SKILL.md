# CRITICAL UNIT-SCALE OVERRIDE: convert WEO GDP only at the Production boundary

The WEO source sheet and the production-function model use different display scales. Preserve the source sheet exactly in its stated IMF scale, but normalize units when the values enter the model.

- `WEO_Data` real GDP (`NGDP_R`) is explicitly labeled **Scale = Billions**. Keep those source observations and post-2027 projection formulas in billions on `WEO_Data`; do not multiply the source sheet itself by 1000.
- The production-function block combines GDP with PWT capital stock and the investment schedule, which are used on a **millions** scale. Therefore every formula that links WEO real GDP into `Production` must convert billions to millions by multiplying the WEO value by **1000**.
- In the historical estimation block, `Production!E6:E27` (Real GDP) must be `WEO_Data` GDP for the matching year `*1000` before `LN(Y)` is computed.
- In the production-function table, column `F` (Y) for 2002-2041 must likewise link the matching `WEO_Data` GDP value `*1000`.
- Do not compensate later by multiplying only `Ystar` or final outputs. The conversion belongs at the WEO-to-Production link so that `LnY`, `LnZ`, HP-filter values, K/Y, Ystar_base, Ystar_with, projected GDP, and growth rates are all internally consistent.

After applying this conversion, recalculate with LibreOffice Calc and sanity-check that recent `Production` Y / Ystar values are on the order of **tens of thousands**, while the corresponding `WEO_Data` source values remain on the order of **tens** because they are still in billions.

All other Round 4 requirements remain mandatory, including fresh-run rebuilding, official bounded PWT/ECB/WEO routes, CFC-to-millions normalization, numeric HP initialization, and final Calc recalculation.

# CRITICAL EXECUTION RECIPE: fresh-run workbook completion

This is a fresh rollout. Assume `test-supply.xlsx` starts from the original blank template even if a previous run built formulas successfully. Rebuild the workbook in this run. The first substantial work must create workbook progress; do not spend the run rediscovering source URLs.

## 1. Build the formula skeleton before source research

Inspect the template once, then populate all formula regions whose references are already determined by the visible sheet/year layout:

- `WEO_Data`: reserve 2000-2027 for sourced IMF values; for 2028-2043 copy the 2027 growth-rate cell by reference and calculate GDP recursively from the previous year's GDP.
- `CFC data`: link each year's capital stock to the matching PWT year and calculate depreciation as CFC divided by capital stock after unit normalization described below.
- `Production!B3`: `AVERAGE` of the most recent eight annual depreciation-rate cells.
- `Production!D6:E27`: links to historical K and real GDP; `F6:F27=LN(K)`, `G6:G27=LN(Y)`; fill the visible productivity-residual / HP-filter formulas and the objective cell.
- Production-function table: historical `K/Y`, K and Y links, recent-nine-year `AVERAGE(K/Y)` anchor for projected K, historical LnZ-trend links, `TREND` extension, `EXP` potential-output formulas, Investment links, capital accumulation using `B3`, K-with-investment, Ystar-with, uplift, projected GDP, and growth formulas.

Save `test-supply.xlsx` immediately after this skeleton exists.

## 2. Use these bounded official source routes

Do not guess filenames or reverse-engineer APIs if the route below works.

### PWT

Use the official Penn World Table bulk workbook from Dataverse:

`https://dataverse.nl/api/access/datafile/554105`

Open/filter the workbook once. On the `Data` sheet filter `countrycode = GEO`; use the `Legend` sheet to confirm `rnna` is capital stock and `rgdpna` is real GDP. Populate the template's two PWT data columns for the matching years, save, and immediately build/recalculate downstream links.

### ECB consumption of fixed capital

Use the official ECB annual Georgia CFC series:

`https://data-api.ecb.europa.eu/service/data/IDCM/A.N.GE.W2.S1.S1.D.P51C.N1G._T._Z.XDC.V.N?startPeriod=1996&endPeriod=2023&format=csvdata`

Populate the CFC observations by year. **Unit normalization is mandatory:** the ECB observations are raw currency-unit amounts while the PWT capital-stock series used by the template is expressed in millions. Convert the ECB CFC amount to millions before dividing by capital stock. In spreadsheet terms the depreciation formula must have the form `CFC / 1000000 / capital_stock`, not simply `CFC / capital_stock`.

After CFC is populated, recalculate and confirm `Production!B3` displays a plausible numeric annual depreciation rate before doing any more source work.

### IMF WEO real GDP and growth

Use the official IMF April 2025 entire-country dataset link exposed by the WEO "Download entire database" page:

`https://www.imf.org/-/media/files/publications/weo/weo-database/2025/april/weoapr2025all.xls`

This download is tab-delimited text despite the `.xls` extension. **Do not use curl/urllib as the primary route when Akamai rejects them. Open it directly with LibreOffice Calc and explicitly import it as tab-delimited text.** A working headless import pattern is:

`soffice --headless --infilter="Text - txt - csv (StarCalc):9,34,76,1" --convert-to xlsx --outdir <tempdir> <URL>`

In the imported sheet, filter:

- `WEO Country Code = 915` / `ISO = GEO`
- `WEO Subject Code = NGDP_R` for real GDP level
- `WEO Subject Code = NGDP_RPCH` for real GDP growth

Copy the 2000-2027 values into `WEO_Data` by year. Then stop IMF research; the post-2027 extension must be formulas in the workbook.

## 3. HP-filter numeric initialization is a blocking checkpoint

Formula structure alone is insufficient. Once PWT and WEO historical values are populated:

1. Recalculate the workbook through LibreOffice Calc so the raw productivity residual (`LnZ`) cells have numeric values.
2. Copy the **evaluated numeric values** of the raw LnZ series into the visible `LnZ_HP` range (`L6:L27`) as the Solver starting values. Do not leave `L6:L27` as formulas that evaluate to blanks.
3. Fill/recalculate the second-difference, residual-check, and HP objective formulas.
4. If Solver is available, minimize the objective by changing `L6:L27`. If Solver cannot be completed promptly, preserve the numeric initialized series and continue; never leave the HP block empty.

## 4. Mandatory Calc recalculation and save

After every major formula/source block, and especially before completion, run the workbook through LibreOffice Calc so formula caches are actually written. Do not let an `openpyxl` save be the final workbook write.

Use a temporary output directory to avoid same-file conversion conflicts, then replace the requested workbook with the recalculated Calc output. Reopen/check the recalculated file and require all of the following before finishing:

- PWT source columns contain data.
- WEO 2000-2027 source values exist and 2028+ GDP cells are formulas.
- CFC depreciation cells evaluate numerically and `Production!B3` is numeric.
- historical LnK/LnY/LnZ cells evaluate numerically.
- `L6:L27` contains numeric HP starting/optimized values.
- production-function and investment-shock output regions evaluate rather than remaining blank.
- no required formula block was erased during the final Calc save.

Once these conditions are met, do not open any new research branch. Save the exact filename `test-supply.xlsx` and finish.

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

## User constraints override generic tool examples

The generic Python examples later in this Skill are defaults, not requirements. Explicit task instructions always take precedence.

- If the task says **Excel only**, **no Python**, **use a spreadsheet app**, or names a browser/spreadsheet interface, do not use pandas/openpyxl/Python as a substitute for the requested workflow.
- If the task forbids hardcoded calculated values, every derived cell must remain an Excel formula. Raw observations collected from an external source may be entered as source data, but ratios, averages, logarithms, projections, trends, depreciation, capital accumulation, and model outputs must be formulas in the workbook.
- If a named browser interface is unavailable but external data are still required, use the most direct official machine-readable/download endpoint available only to obtain the source observations. Do not move the requested Excel calculations into a script merely because retrieval is easier there.
- Never let a generic recommendation in this Skill silently override an explicit user constraint.

## Reading and analyzing data

### Data analysis with pandas
For data analysis, visualization, and basic operations, use **pandas** when the user has not prohibited Python and has not required a different spreadsheet-only workflow:

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

### Budgeted source-to-workbook workflow for research-heavy templates

When an existing workbook must be completed from several online sources, **workbook progress is the primary completion signal**. Do not consume most of the execution budget researching sources while the workbook remains blank.

1. **Inspect once, then map the workbook contract.** At the start, identify the exact destination workbook, required sheets, year ranges, source-data columns, assumption cells, and formula/model regions. Preserve the template and save to the required output filename immediately if needed.
2. **Create a dependency order.** Collect the source blocks that feed the most downstream formulas first. For each source, know exactly which cells it unlocks before browsing.
3. **Timebox each access path.** After at most a few unsuccessful attempts to discover or parse the same source through one route, switch to another official route. Do not repeatedly guess filenames, scrape the same HTML with slightly different patterns, poll a slow parser, or keep reverse-engineering a site while no workbook cells are being completed.
4. **Prefer explicit official download links over filename guessing.** If an official landing page says the data are available below, inspect the actual link targets and follow them. Do not spend many actions probing invented URLs when the page already exposes an official download/API target.
5. **Persist every completed source immediately.** As soon as one source block is available, enter/link it into its required sheet, add requested source documentation/comments, save the workbook, and build any formulas that depend only on that block before researching the next source.
6. **Use efficient reads for large workbooks.** Never perform repeated random-access cell reads across a large `.xlsx` when a single sequential read, metadata/legend lookup, or filtered import can answer the question. If the task itself forbids Python, use the spreadsheet application's import/filter tools instead of scripting around that constraint.
7. **Do not research past the point of sufficiency.** Once the variable names, units, year coverage, and required observations are known, stop investigating the source and populate the workbook.
8. **Reserve the final phase for formulas and validation.** By the latter part of the execution, stop nonessential source exploration. Finish formulas, cross-sheet links, model extensions, recalculation, and sanity checks with the data already collected.

Use this progress invariant throughout the task:

`inspect template -> obtain one required source -> write it into workbook -> build unlocked formulas -> save -> next source`

Do **not** use this failure pattern:

`inspect -> browse -> probe URLs -> parse -> browse again -> parse again -> research another source -> reach the action limit with an almost-empty workbook`.

### Completion gates for formula-driven economic/financial models

Before declaring completion, reopen the saved workbook and verify all of the following against the user's requested model rather than merely checking that the file exists:

- Every required source-data range is populated for the requested years.
- Every requested calculated field is a formula, not a hardcoded result.
- Assumption cells that should aggregate historical observations use formulas referencing those observations.
- Cross-sheet values are linked with formulas instead of copied when the task asks for links.
- Projection years contain formulas through the full requested horizon.
- Optimization/filter/trend areas have numeric outputs after recalculation, not just placeholder formulas or blanks.
- Model outputs have plausible units and magnitudes and no formula errors.
- The workbook has been saved to the exact required filename.

## Common Workflow
1. **Choose tool**: obey explicit user constraints first; otherwise pandas for data and openpyxl for formulas/formatting
2. **Create/Load**: Create new workbook or load existing file
3. **Modify**: Add/edit data, formulas, and formatting
4. **Save**: Write to file
5. **Recalculate formulas (MANDATORY IF USING FORMULAS)**: Use the allowed spreadsheet/recalculation workflow. When Python is allowed, the provided recalc.py can be used:
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
# Using openpyxl for formulas and formatting when Python is permitted
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
# Using openpyxl to preserve formulas and formatting when Python is permitted
from openpyxl import load_workbook

wb = load_workbook('existing.xlsx')
sheet = wb.active  # or wb['SheetName'] for specific sheet

for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    print(f"Sheet: {sheet_name}")

sheet['A1'] = 'New Value'
sheet.insert_rows(2)
sheet.delete_cols(3)

new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

## Recalculating formulas

Excel files created or modified by openpyxl contain formulas as strings but not calculated values. When Python is permitted, use the provided recalc.py script to recalculate formulas:

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
- [ ] **NaN handling**: Check for null values with `pd.notna()` when pandas is allowed
- [ ] **Far-right columns**: FY data often in columns 50+
- [ ] **Multiple matches**: Search all occurrences, not just first
- [ ] **Division by zero**: Check denominators before using `/` formulas (#DIV/0!)
- [ ] **Wrong references**: Verify all cell references point to intended cells (#REF!)
- [ ] **Cross-sheet references**: Use correct format (Sheet1!A1)

### Formula Testing Strategy
- [ ] **Start small**: Test formulas on 2-3 cells before applying broadly
- [ ] **Verify dependencies**: Check all cells referenced in formulas exist
- [ ] **Test edge cases**: Include zero, negative, and very large values

### Interpreting recalc.py Output
The script returns JSON with error details:
```json
{
  "status": "success",
  "total_errors": 0,
  "total_formulas": 42,
  "error_summary": {
    "#REF!": {
      "count": 2,
      "locations": ["Sheet1!B5", "Sheet1!C10"]
    }
  }
}
```

## Best Practices

### Library Selection
- **pandas**: Best for data analysis, bulk operations, and simple data export when Python is permitted
- **openpyxl**: Best for complex formatting, formulas, and Excel-specific features when Python is permitted
- **Spreadsheet application**: Required when the task explicitly demands Excel/spreadsheet-only execution or interactive Solver/filter behavior

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
