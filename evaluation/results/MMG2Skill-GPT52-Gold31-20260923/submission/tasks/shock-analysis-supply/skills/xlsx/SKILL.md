---
name: xlsx
description: Comprehensive spreadsheet creation, editing, and analysis with support
  for formulas, formatting, data analysis, and visualization—while keeping all *calculations*
  inside Excel via formulas and delivering an error-free workbook.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. **Open and map the template first (before downloading anything):**
   - Load `test-supply.xlsx` and inspect each required sheet (`PWT`, `WEO_Data`, `CFC data`, `Production`, `Investment`) to identify the exact input columns/rows to populate and the exact cells meant for formulas vs. raw data.
   - Do **not** stop after inspection—immediately proceed to fill the mapped inputs and insert formulas where the template expects them.
2. **Collect WEO data using Playwright MCP (no curl/terminal-only workflow):**
   - Use Playwright to navigate the IMF WEO database and obtain **Georgia** series for:
     - Real GDP **level** (2000–2027)
     - Real GDP **growth rate** (2000–2027)
   - Export/download the resulting table (or copy from the page) and populate the corresponding rows in `WEO_Data`.
   - Extend growth **from 2028–2043** by **linking** each year’s growth to the 2027 growth cell (absolute reference to the 2027 cell), and compute projected GDP levels with Excel formulas (e.g., prior_year_GDP * (1+growth)) rather than hardcoding computed values.
3. **Get PWT from the official PWT page, but use the Dataverse direct file when needed for reliability:**
   - Preferred: download from the PWT site.
   - If the site routes to Dataverse, download PWT 11.0 Excel via Dataverse “access/datafile” endpoint (this is acceptable as the same source file).
   - When extracting PWT variables, **read from the `Data` sheet** (not `Info`) and use an efficient row-iterator approach (e.g., `iter_rows(values_only=True)`) to avoid stalls on large sheets.
   - Use the `Legend`/metadata sheet to confirm variable meanings before populating `PWT` (e.g., `rnna`, `rkna`, `delta`, etc.), then paste Georgia (GEO) time series into the correct columns in `PWT` as raw values.
4. **Collect ECB “Consumption of fixed capital” and compute depreciation rate in-sheet:**
   - Use Playwright to navigate the ECB Georgia page and retrieve annual “Consumption of fixed capital” series.
   - Paste values into **Column C** of `CFC data`.
   - Link capital stock from `PWT` into the specified `CFC data` capital-stock column via sheet references (green-links convention if formatting exists).
   - Compute depreciation rate in `CFC data` using Excel formulas (no Python-side computation), referencing CFC and capital stock columns as instructed by the template.
5. **Set `Production` sheet depreciation assumption exactly as required:**
   - In `Production!B3`, set a formula that equals the **average depreciation rate of the most recent 8 years** from the depreciation-rate column you computed in `CFC data` (use `AVERAGE(last_8_cells_range)` with correct anchored range).
6. **HP filter setup must be formula-driven and Solver-ready inside the workbook:**
   - Link required K and Y series into `Production!D6:D27` and `E6:E27`.
   - Compute `LnK` and `LnY` with Excel `LN()` formulas.
   - For HP filter area:
     - Link/initialize `LnZ` to the designated column (per template hint).
     - Duplicate the `LnZ_HP` column as placeholder (cells should reference the decision-variable range, not hardcoded).
     - Compute second-order differences and sanity check so the “LnA-Trend check” column is **0 before solving** (i.e., built from formulas that evaluate to 0 given placeholder equality).
     - Define the objective cell (e.g., `P5`) as the sum of squared residual + lambda * sum of squared second-differences (all formulas).
   - Configure Solver target: **minimize objective** by changing the `LnZ_HP` decision range (e.g., `L6:L27`). (If the environment cannot execute Solver, still leave a fully configured, formula-consistent sheet where Solver can be run without edits.)
7. **Production function + capital path extension + investment shock must respect units and the 6.5bn total constraint:**
   - Link K and Y from their source sheets (K latest 2023, Y latest 2025, and projected Y from `WEO_Data`).
   - Compute K/Y for 2002–2023 and extend K using an anchor equal to **average K/Y of most recent 9 years** (Excel `AVERAGE()` over the correct range; then `K = (anchored_KY)*Y`).
   - Extend `LnZ` trend to 2041 using Excel `TREND()` and calculate `Ystar_base` via the Cobb–Douglas equation using sheet-linked inputs (no hardcoded computed outputs).
   - In `Investment`, implement an 8-year investment stream (2026–2033) whose **sum equals exactly 6.5bn USD in the workbook’s units**:
     - Put the total (6.5bn in correct unit) in a single assumption cell.
     - Use formulas to allocate across 8 years (e.g., equal split = total/8, or the template’s intended profile), and use `SUM()` to verify the total equals the assumption cell.
   - Link investment into `Production`, compute `ΔK`, `K_with`, and `Ystar_with` using Excel formulas only.
8. **Save and verify formula integrity:**
   - Save updates into `test-supply.xlsx` (same filename as required).
   - Recalculate with `python recalc.py test-supply.xlsx` and fix until:
     - **Zero Excel errors** (#REF!, #DIV/0!, #VALUE!, #NAME?, #N/A)
     - Formulas remain present in all calculation cells (no value-only replacements).
## Expected Result
`test-supply.xlsx` is fully populated with Georgia data (PWT, WEO, ECB CFC), includes all required cross-sheet links and formulas for depreciation, HP-filter setup, Cobb–Douglas potential output, capital extension, and the 8-year investment shock summing to 6.5bn (in consistent units), and recalculates with **zero formula errors**.
