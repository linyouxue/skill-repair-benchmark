# SKILL.md

## When to use
Use this skill when a task requires completing a multi-step **Excel-only** workflow that:
- Imports time-series commodity price data from an external IMF-style Excel source into a specified workbook sheet.
- Computes **log returns** and **rolling volatilities** (e.g., 3‑month and 12‑month), including an **annualization** step and percent scaling.
- Extracts and reconciles **country-level 2025 gold reserve values** across multiple sheets (e.g., “Value” vs “Volume”), converting volumes to values using a specified **proxy gold price average**.
- Uses Excel lookups (e.g., `XLOOKUP` or `INDEX`+`MATCH`) to join with **total reserves**, filters out countries missing required year data, and computes a final **risk metric** (RaR) into an “Answer” sheet.
- Produces and saves a final workbook to a required path.

Before acting, gather evidence by:
- Opening the provided workbook and confirming required sheet names exist and where inputs/outputs are expected (exact rows/columns for blanks/tables).
- Inspecting the source commodity file’s date frequency/format and the gold price series column/units.
- Locating where 2025 data lives in each relevant sheet and how “country”, “year”, “value/volume”, and “total reserves” are laid out.

## Possible Failure Modes
- **Wrong return definition**: using simple returns `(Pt/Pt-1 - 1)` instead of `LN(Pt/Pt-1)`.
- **Wrong scaling**: forgetting to multiply log returns by 100 before volatility (or multiplying twice).
- **Wrong windowing**: computing “3‑month volatility” on 3 data points instead of returns over a 3-month window (returns count is typically months-1); or inconsistent window definition across columns.
- **Incorrect annualization**: annualizing the wrong statistic (e.g., annualizing returns instead of volatility), or using the wrong factor (monthly → annual volatility typically `*SQRT(12)`).
- **Stale “latest” selection**: not actually using the most recent available month when picking the volatility used in downstream steps.
- **Date misalignment**: gold price series not monthly, contains non-month-end entries, or mixed text/date types causing lookups/rollups to skip rows.
- **Incomplete country coverage**: missing countries that appear in “Volume” with 2025 data but not in “Value”; or accidentally duplicating countries.
- **Wrong 2025 proxy price**: using the wrong months for the Jan–Sep average, mixing up current year vs another year, or averaging levels with missing months.
- **Unit mismatch in conversion**: converting volume→value without confirming volume unit basis vs the price unit (troy ounces vs metric tonnes) and required workbook expectations.
- **Lookup errors**: `XLOOKUP`/`MATCH` targeting wrong year column, approximate match when exact required, or not locking ranges (`$`) leading to shifted references when filling formulas.
- **Not deleting ineligible rows**: failing to remove countries lacking 2025 total reserves before computing RaR, which can propagate `#N/A`/`#VALUE!`.
- **Breaking the workbook**: overwriting headers, table ranges, named ranges, or formulas outside specified fill areas.
- **Violating constraints**: performing computations outside Excel (e.g., in Python) when the task requires Excel formulas for calculations.

## Possible procedures
1. **Prepare the workbook layout (no computations yet)**
   - Open the workbook; locate the “Gold price” sheet and the target columns for price, log return, 3‑month vol, 12‑month vol.
   - Locate the “Answer” sheet and identify all blanks/tables to populate for each step.
   - Identify “Value”, “Volume”, and “Total Reserves” sheet structures: where the 2025 data sits (rows vs columns), and the country identifiers used.

2. **Import gold price time series into the “Gold price” sheet**
   - Download/open the external commodity database file and locate the gold price series in **US$ per troy ounce**.
   - Copy/paste values (and dates) into the destination sheet, preserving chronological order and consistent date types.
   - Recovery check: verify the imported series is numeric, monthly, and that the latest month is truly the last row.

3. **Compute monthly log returns (percent)**
   - In the log-return column, use a formula of the form `=LN(current_price/previous_price)*100`.
   - Ensure the first return row is blank/`NA()` as appropriate (no prior month).
   - Fill down to the end of the dataset; lock references only where needed.
   - Recovery check: spot-check a couple of months manually (sign and magnitude) to confirm plausibility.

4. **Compute rolling volatilities (3‑month and 12‑month)**
   - Use rolling standard deviation on the **log return series**:
     - 3‑month window: standard deviation over the last 3 monthly returns (or the workbook’s specified convention—match what the sheet labels imply).
     - 12‑month window: standard deviation over the last 12 monthly returns.
   - Apply annualization consistently (commonly multiply monthly-return stdev by `SQRT(12)` if the task expects annualized volatility).
   - Ensure “latest” volatility used later is taken from the last available completed window.
   - Recovery check: confirm the last rows don’t show `#DIV/0!` due to insufficient window length; ensure the final “latest” cell references the intended row.

5. **Populate Step 1 outputs in “Answer”**
   - Link “Answer” cells directly to the computed cells in “Gold price” (avoid hard-coding).
   - For any “3‑months annualized” requirement, calculate it *from* the 3‑month volatility per instructions (don’t re-derive from raw prices).
   - Recovery check: ensure all Step 1 blanks are filled and update dynamically if source cells change.

6. **Build the Step 2 country list (2025 gold reserves value)**
   - From “Value” sheet, identify all countries with 2025 gold reserves value; list them in the Step 2 area on “Answer”.
   - Then check “Volume” sheet for additional countries that have 2025 data but are absent from “Value”.
     - For those, convert volume→value using the specified proxy price: **Jan–Sep average** of 2025 gold price.
   - Compute the “gold price exposure” row as instructed (treat as near-term valuation swing measure); ensure it references the volatility/price inputs required by the workbook logic.
   - Recovery check: confirm no missing/duplicate countries; conversion uses the correct price average and consistent units.

7. **Replicate into Step 3 and join with Total Reserves**
   - Copy the Step 2 outputs (countries, gold reserve value, relevant gold price volatility) into the Step 3 table region as values or formulas (prefer formulas to keep consistency).
   - Use `XLOOKUP` or `INDEX`+`MATCH` to retrieve each country’s **2025 total reserves** from “Total Reserves”.
     - Use exact match on country; exact match on year/column.
   - If a country lacks 2025 total reserves, remove that row from the Step 3 table (as required) and ensure downstream formulas exclude it.
   - Compute RaR using the table inputs, referencing cells rather than typing numbers.
   - Recovery check: ensure no `#N/A` remains in Step 3; RaR formulas reference the final filtered list only.

8. **Save final artifact**
   - Save the completed workbook to the required output path exactly.
   - If the environment produces compatibility prompts, keep it in `.xlsx` format.

## Verification Checklist
- [ ] Source gold price data is imported as **monthly numeric series** with correct units; last row corresponds to the latest month.
- [ ] Log return formula uses `LN(Pt/Pt-1)` and is scaled by `*100` exactly once.
- [ ] 3‑month and 12‑month volatility are computed on the **log return** series using the intended rolling windows; “latest” volatility references the last valid window.
- [ ] Annualization (if required) is applied to the correct volatility metric using a consistent factor (e.g., monthly → annual via `SQRT(12)`), and any “3‑months annualized” value is derived from the 3‑month volatility per instructions.
- [ ] All Step 1 “Answer” blanks are filled via cell references (not hard-coded) and update if upstream cells change.
- [ ] Step 2 includes all countries with 2025 data from “Value” plus any additional eligible countries from “Volume”; no duplicates.
- [ ] Volume-only countries’ values are converted using the **Jan–Sep average** proxy gold price for 2025 (correct months, correct year).
- [ ] Step 3 reproduces the Step 2 set, then **removes** any country lacking 2025 total reserves data; no `#N/A`/`#VALUE!` remains in the final table.
- [ ] `XLOOKUP`/`INDEX`+`MATCH` use exact matches and locked ranges where appropriate; formulas fill down correctly.
- [ ] RaR is computed only from the final valid Step 3 rows and matches the workbook’s expected logic/units.
- [ ] No unrelated sheets/structures were overwritten; only intended cells/tables were modified.
- [ ] All computations are done in **Excel formulas** (no external calculation substituted).
- [ ] File is saved successfully to `/root/output/rar_result.xlsx` and opens without repair warnings.
