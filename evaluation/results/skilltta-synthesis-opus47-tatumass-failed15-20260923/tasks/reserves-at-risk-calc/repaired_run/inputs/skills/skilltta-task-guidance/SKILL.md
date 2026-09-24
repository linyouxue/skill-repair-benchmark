---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill for multi-step Excel workbook tasks that require:
- Downloading an external data source (e.g., an IMF/commodity workbook) and extracting a specific series into a named sheet.
- Populating designated cells across multiple sheets with **Excel formulas** (not precomputed Python values), because the instruction restricts computation to Excel.
- Performing financial-style calculations: log returns, rolling volatilities (annualized), cross-sheet lookups (INDEX/MATCH or XLOOKUP), and a final risk metric such as Reserves-at-Risk (RaR).
- Saving the final workbook to an exact output path.

Before acting, the agent should gather:
- The exact structure of the target workbook: sheet names, row/column layout of each "Answer" block, and any HINTs (e.g., "multiply log returns by 100").
- The exact URL/source and which series/units to extract (e.g., "US$ per troy ounce").
- Which rows correspond to which sub-step, and the expected formula semantics (latest value vs. average vs. annualized).
- Whether openpyxl (or similar) is used to write formulas as strings while preserving existing sheet content and formatting.

## Possible Failure Modes
- Hardcoding numeric results into cells instead of writing Excel formulas — violates "only use Excel for formula, computation, etc."
- Downloading the wrong sheet/series from the source workbook (commodity files often have many series; pick gold in USD/troy oz, monthly frequency).
- Misaligning the monthly time series (e.g., off-by-one when computing log return `LN(P_t/P_{t-1})`, or forgetting to multiply by 100 per HINT).
- Volatility mistakes:
  - Using population vs. sample stdev inconsistently.
  - Forgetting annualization factor (`*SQRT(12)` for monthly data).
  - Using the wrong rolling window (3 vs. 12) or not using the *latest* window for the Answer sheet.
- STEP 2 errors:
  - Missing countries that appear only in the Volume sheet with 2025 data — must be added and converted to Value using Jan–Sep 2025 average gold price.
  - Using annual or wrong-period average instead of Jan–Sep average as the 2025 price proxy.
- STEP 3 errors:
  - Using VLOOKUP or hardcoded joins instead of INDEX+MATCH / XLOOKUP as instructed.
  - Failing to delete countries lacking 2025 Total Reserves data before computing RaR.
  - RaR formula misapplied (typical form: `Gold Value × Volatility × Total Reserves ratio`, or `Gold Value / Total Reserves × Volatility` — follow the sheet's row semantics).
- Overwriting or destroying existing sheets/formatting when writing with openpyxl (use `load_workbook`, don't recreate).
- Saving to the wrong path or wrong extension; the target expects `/root/output/rar_result.xlsx` exactly.
- Copying concrete numbers, sheet layouts, or country lists from retrieved BigCodeBench examples — those are unrelated pandas exercises, not templates for this task.

## Possible procedures
1. **Fetch source data**
   - Download the IMF global commodity Excel from the given page. Inspect sheet names; locate the monthly gold price series in USD per troy ounce.
   - Copy the (Date, Price) columns into the workbook's "Gold price" sheet, starting where the template expects.

2. **Compute return/volatility formulas (in Excel)**
   - Column C (monthly log return): `=LN(B3/B2)*100` from the second data row onward.
   - Column D (3-month volatility): rolling stdev of last 3 log returns, annualized: `=STDEV(C_{t-2}:C_t)*SQRT(12)`.
   - Column E (12-month volatility): `=STDEV(C_{t-11}:C_t)*SQRT(12)`.
   - Decide STDEV vs STDEV.S consistently; document choice.

3. **Fill Answer STEP 1 (rows 3–6)**
   - Use references to the *latest* available row in "Gold price" for 3-mo and 12-mo volatility.
   - For the "3-month annualized" cell, derive from the 3-month volatility cell (already annualized if using SQRT(12); otherwise apply the annualization here).

4. **STEP 2 (rows 11–13)**
   - From "Value" sheet: list every country with a non-empty 2025 value; write country names and values via cell references.
   - Cross-check "Volume" sheet: any country with 2025 volume data but absent from "Value" must be appended; compute Value = Volume × (Jan–Sep 2025 average gold price, referenced via `AVERAGE` over the relevant Jan–Sep cells in "Gold price").
   - Row 13 "Gold price exposure": sum or per-country exposure — read the row label to confirm; typically total gold reserves value.

5. **STEP 3 (rows 20–24)**
   - Copy country list, values, and volatility from STEP 2 by cell reference.
   - Row 23 Total Reserves 2025: use `=INDEX(TotalReserves!range, MATCH(country, TotalReserves!keys, 0))` or `=XLOOKUP(country, keys, values2025, "")`.
   - Remove (delete row / blank out) any country whose lookup returns no 2025 data before computing RaR.
   - Row 24 RaR: apply the formula implied by the sheet header (commonly `Gold Value × Volatility / Total Reserves` — verify against the template's row labels).

6. **Persist**
   - Open the template with `openpyxl.load_workbook`, write formulas as strings (starting with `=`), save to `/root/output/rar_result.xlsx`. Ensure `/root/output` exists.

Decision points / recovery checks:
- If the IMF workbook layout changed, search sheets for the string "Gold" and unit "troy" to locate the correct column.
- If volatility cells show `#DIV/0!` or `#NUM!`, verify enough prior rows exist for the rolling window.
- If XLOOKUP is unavailable in the Excel engine used, fall back to INDEX+MATCH.
- If unsure whether a country belongs in STEP 2's "Volume-only" additions, verify it truly has 2025 data and is truly absent from Value (case/whitespace-normalize names).

## Verification Checklist
- [ ] `/root/output/rar_result.xlsx` exists and opens cleanly.
- [ ] "Gold price" sheet contains monthly gold USD/troy oz data with columns C (log return ×100), D (3-mo annualized vol), E (12-mo annualized vol), all as **Excel formulas**, not literal numbers.
- [ ] STEP 1 answer cells (rows 3–6) reference the latest row of "Gold price" and include the correctly annualized 3-month figure.
- [ ] STEP 2 (rows 11–12) includes every 2025 country from "Value" plus any 2025-only countries from "Volume", with the latter's values computed as `Volume × AVERAGE(Jan–Sep 2025 gold price)` via formula.
- [ ] Row 13 gold price exposure is a formula, consistent with the row's intent.
- [ ] STEP 3 (rows 20–22) mirrors STEP 2 via cell references; row 23 uses INDEX+MATCH or XLOOKUP against a Total Reserves sheet; countries without 2025 total reserve data are removed.
- [ ] Row 24 RaR formula is present and evaluates to a finite number for every remaining country.
- [ ] No cells contain hardcoded results where a formula is required; no computation was done outside Excel and pasted as values.
- [ ] Existing sheets, headers, and formatting from the template are preserved; only intended cells were modified.
- [ ] Nothing was copied from unrelated retrieved examples (they are generic pandas tasks, not templates).
- [ ] Recovery: if any formula shows an error (`#N/A`, `#DIV/0!`, `#REF!`), trace the referenced range and fix before finalizing.
