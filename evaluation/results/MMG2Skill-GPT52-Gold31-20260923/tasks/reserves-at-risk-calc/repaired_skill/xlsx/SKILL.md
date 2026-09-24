---
name: xlsx
description: Create/edit existing Excel workbooks with **openpyxl + pandas**, using
  **Excel formulas (not Python hardcodes)** for computations, and validating via **LibreOffice
  recalc.py** so the delivered file has **zero formula errors** while preserving the
  template’s structure and conventions.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. **Load the provided template and preserve it**
   - Open with `openpyxl.load_workbook(path)` (do **not** use `data_only=True` if you will save).
   - Keep existing sheet layout, formatting, and any template formulas unless you confirm a cell is truly disposable.
2. **Bring in external data (e.g., IMF commodity database)**
   - Download the source file (e.g., IMF “external-data.xlsx” from the provided page).
   - Use `pandas.read_excel(...)` to inspect and extract the needed series (e.g., Gold price, US$ per troy ounce).
   - Write the **raw monthly values** into the target sheet/range in the template (values only for the data column), preserving headers/spacing conventions already used.
3. **Compute results in Excel via formulas (not Python)**
   - Insert formulas for required outputs (e.g., monthly log returns, rolling volatilities, annualization) directly into the workbook cells.
   - Use `IFERROR(...)` where appropriate to prevent propagation of upstream blanks into visible #N/A/#DIV/0! errors.
4. **Ensure LibreOffice-compatible formulas (avoid #NAME?)**
   - Prefer function names supported by LibreOffice in this environment:
     - Use `STDEV(...)` (sample) rather than `STDEV.S` if `STDEV.S` triggers `#NAME?`.
     - Use `NORMSINV(...)` (or `NORMINV(p,0,1)`) rather than `NORM.S.INV` if `NORM.S.INV` triggers `#NAME?`.
   - If lookup functions error under LibreOffice, fall back to widely supported patterns (e.g., `INDEX(..., MATCH(...))`) instead of relying on newer functions.
5. **Do not “fix” errors by blanking template cells unless validated**
   - If recalc shows an error in a template cell:
     - First check whether it contains a **formula** or is **referenced** by required outputs.
     - Prefer correcting the incompatible function or wrapping downstream references with `IFERROR` rather than clearing the cell.
     - Only clear a cell when you have confirmed it is an unintended stray error value and not part of the intended model logic.
6. **For “find all countries with 2025 data”, scan the full sheet width (no fixed-column assumptions)**
   - Programmatically locate the **2025** position by scanning header rows/columns (don’t assume it is in the first N columns).
   - Iterate across **all country columns (or rows)** for that year and collect every non-empty numeric entry.
   - Populate the Answer table from that complete discovered set, using cell links/formulas back to the source sheet cells (not hardcoded numbers).
7. **Recalculate and validate (mandatory)**
   - Run: `python recalc.py <file.xlsx> [timeout]`.
   - If `status="errors_found"`, patch exactly the reported cells/functions, then rerun until `total_errors = 0`.
8. **Save the final workbook**
   - Write to the user-required path (e.g., `/root/output/rar_result.xlsx`), then perform one final recalc check on that saved file.
## Expected Result
- The updated workbook preserves the template’s structure and formulas where intended, includes the imported data and required computations, and **LibreOffice recalculation returns `total_errors: 0`** (no `#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, or `#NAME?`).
