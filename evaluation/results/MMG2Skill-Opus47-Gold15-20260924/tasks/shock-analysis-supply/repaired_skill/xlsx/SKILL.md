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
### Solver-Required Cells (CRITICAL for tasks that say "use Solver")
- When the task instruction explicitly says "use Solver in excel" (e.g., HP filter smoothing), the adjustable cells (e.g., L6:L27) MUST remain as either (a) placeholder formulas like `=K{row}` seeded to the input series, or (b) blank/zero cells to be modified by Excel's Solver — NEVER hard-coded numeric values computed in Python.
- Do NOT solve the optimization analytically in Python (e.g., numpy closed-form HP filter) and write the results into the adjustable range. This violates the "no python, no hardcoded numbers for cells that needs calculation" rule even if the objective value is mathematically equivalent.
- Acceptable pattern: build the objective cell (e.g., P5 = `=SUMSQ(N6:N27)+lambda*SUMSQ(M7:M26)`), leave adjustable cells as `=K6`…`=K27` placeholders, and document in a cell comment or an adjacent cell that the user must run Solver (Data → Solver → Set Objective P5 to Min, By Changing L6:L27, GRG Nonlinear). The workbook is delivered "Solver-ready", not "Solver-solved".
- If a headless environment cannot run Excel Solver, still leave the adjustable cells as placeholder formulas — do not substitute Python-computed constants.
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
### Unit Reconciliation (CRITICAL for cross-source economic data)
- Before dividing / multiplying series from different sources, confirm units match on BOTH dimensions:
  - **Currency**: nominal domestic currency (e.g., GEL) vs. real USD (e.g., 2017 US$). PWT `rnna` is millions of 2017 US$; ECB CFC for Georgia is millions of nominal GEL. These cannot be divided directly.
  - **Real vs. nominal**: deflate nominal series with a matching deflator (e.g., GDP deflator) before comparison.
  - **Scale**: millions vs. billions vs. units.
- For the depreciation-rate calculation on the "CFC data" sheet: CFC (ECB, GEL nominal) must be converted to millions of 2017 US$ before dividing by PWT `rnna`. A plausible depreciation rate for Georgia is ~4% (compare against PWT's own `delta` series as a sanity check). If the computed δ is far from ~4% (e.g., 2.3%), the units are almost certainly mismatched.
- If FX / deflator data is unavailable in the workbook, add source cells (with citations) rather than skipping the conversion. Never let a dimensionally-meaningless ratio propagate into downstream ΔK / Ystar_with.
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
**Always use Excel formulas instead of calculating values in Python and hardcoding them.** This ensures the spreadsheet remains dynamic and updateable. This rule applies with special force to:
- Cells the task designates as **Solver adjustable variables** (leave as placeholder formulas — see "Solver-Required Cells" above)
- Cells the task says to compute via a specific Excel formula (e.g., "use formula to calculate", "calculate using column C&D", "use TREND to extend")
- Any downstream cell that depends on a calculation chain
### ❌ WRONG - Hardcoding Calculated Values
```python
# Bad: Calculating in Python and hardcoding result
total = df['Sales'].sum()
sheet['B10'] = total  # Hardcodes 5000
# Bad: Solving HP filter in numpy and writing trend into L6:L27
trend = np.linalg.solve(A, b)
for i, v in enumerate(trend):
    sheet.cell(row=6+i, column=12, value=float(v))  # VIOLATES Solver requirement
```
### ✅ CORRECT - Using Excel Formulas
```python
# Good: Let Excel calculate the sum
sheet['B10'] = '=SUM(B2:B9)'
# Good: Seed Solver adjustable cells with placeholder formulas
for r in range(6, 28):
    sheet.cell(row=r, column=12, value=f'=K{r}')  # L6:L27 placeholder = LnZ
# Then instruct user to run Data → Solver → Min P5 by changing L6:L27
```
## Data Sourcing Discipline
- When the task names a specific data source and tool (e.g., "Use Playwright MCP", "Get from ECB link"), attempt the specified route first. If the tool is unavailable in the environment, document that limitation in a cell comment / source note rather than silently substituting transcribed numbers.
- For PWT: use the official PWT 10.01 download from rug.nl. Column B is `rnna` (capital stock at constant 2017 national prices, millions of 2017 US$). Only fill years the source actually publishes (PWT 10.01 ends at 2019); do NOT extrapolate rnna 2020-2023 with a CAGR unless the task specifically asks — instead leave those years blank or clearly mark them as agent-extrapolated with a source note. Downstream, the "K in 2023" input for the Production sheet should come from the extended K series built in Production (rows 36-57), not from a fabricated PWT tail.
- For column C of PWT: the task says "fill relevant data" and hints at reading the PWT metadata. The typical companion series is `delta` (average depreciation rate of the capital stock) — this is also the sanity-check benchmark for the CFC-based δ on the "CFC data" sheet.
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
7. **Sanity-check economic outputs**: after recalc, spot-check that key ratios/rates fall in plausible ranges (e.g., depreciation rate 3-6% for an emerging economy, capital's share 0.3-0.5, HP-filter residuals near zero). Anomalies usually indicate a unit or reference bug.
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
- [ ] **Solver adjustable cells stay as formulas/placeholders, not numeric constants**
- [ ] **Unit dimensions match** across every division/multiplication involving cross-source data
### Common Pitfalls
- [ ] **NaN handling**: Check for null values with `pd.notna()`
- [ ] **Far-right columns**: FY data often in columns 50+
- [ ] **Multiple matches**: Search all occurrences, not just first
- [ ] **Division by zero**: Check denominators before using `/` in formulas (#DIV/0!)
- [ ] **Wrong references**: Verify all cell references point to intended cells (#REF!)
- [ ] **Cross-sheet references**: Use correct format (Sheet1!A1) for linking sheets
- [ ] **Unit mismatch**: Nominal-currency series divided by real-USD series produces a garbage rate — always reconcile units first
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
