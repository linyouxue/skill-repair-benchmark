---
name: xlsx
description: Create, edit, and analyze .xlsx files (often from a provided template)
  using Excel formulas for all computations, with unit-consistent finance math (returns/volatility/VaR-style
  exposure), robust lookups, and safe verification/recalculation.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. **Open and inspect the workbook/template before writing anything**
   - Load with `openpyxl.load_workbook(..., data_only=False)` and identify the exact input columns/rows and any pre-existing conventions/formulas.
   - **Preserve the template exactly** (layout, headers, styles, existing formulas). Template conventions override any generic standards.
   - Keep standard model conventions when the template is silent: blue = inputs, black = formulas, green = internal links, red = external links; keep consistent number formats (currency, %, negatives in parentheses, etc.).
   - Never save a workbook you opened with `data_only=True` (it can overwrite formulas with values).

2. **Bring in source data (values only) without breaking template formulas**
   - Use pandas to read external workbooks for extraction, but write the extracted series into Excel as raw values **only in the intended input columns** (typically date + price). Do not overwrite calculation columns (log returns/volatility) if they already have formulas.
   - Align pasted values to the template’s expected date order/range (don’t shift dates vs prices); detect the last populated row after paste and use that as the end of all fill ranges.

3. **Compute log returns + rolling vol by mirroring the template’s convention (don’t invent the definition)**
   - **First choice:** if the template already has formulas in the “Gold price” calculation columns (e.g., C:D:E), keep them and just fill down to the last data row.
   - If formulas are missing and you must create them, match the template’s unit style:
     - If the return cells are stored as “percent points” (hint-driven), use `*100`; if the cells are true `%` formatted decimals, **do not** multiply by 100.
     - **Monthly log return (in the same unit you will later vol on):**  
       `=IF(OR(curr_price="",prev_price=""),"",LN(curr_price/prev_price)*scale)`  
       where `scale` is `100` for percent-points, otherwise `1`.
     - **Rolling vol:** use the same STDEV variant the template uses elsewhere (scan any existing volatility formulas); if the template gives no signal, default to **`STDEV.S`**.
       - **3-month volatility (trailing 3 monthly log returns):** `STDEV.S(last_3_returns)`
       - **12-month volatility (trailing 12 monthly log returns):** `STDEV.S(last_12_returns)`
     - Only annualize inside the rolling-vol columns if the template’s headers/formulas clearly indicate “annualized”; otherwise keep the rolling vols in the same units as the underlying monthly returns.
   - Keep early rows blank with `IF(...)` guards (no `#DIV/0!`, `#VALUE!`, etc.).

4. **Populate “Answer” STEP 1 using the row of the latest price (avoid “last numeric in vol column” pitfalls)**
   - For the 95% one-sided z-score, use: `=NORMSINV(0.95)`.
   - When the instruction says “use the latest data”, first locate the last numeric **price** row, then pull the vol from that row (so stray numeric cells below can’t hijack “latest”):
     - Latest 3‑month vol:  
       `=INDEX('Gold price'!D:D, MATCH(9.99999999999999E+307,'Gold price'!B:B))`
     - Latest 12‑month vol:  
       `=INDEX('Gold price'!E:E, MATCH(9.99999999999999E+307,'Gold price'!B:B))`
   - For “3‑month annualized”, compute it directly from the 3‑month volatility cell in Answer (so scaling is explicit and traceable):  
     `=C4*SQRT(12)`.

5. **Use robust country/year links and lookups (keep what worked)**
   - Pull 2023 gold reserve **values** directly from the `Value` sheet via links (don’t retype).
   - If a country exists in `Volume` (has 2023 data) but not in `Value`, convert volume→value using **Jan–Sep 2023 average gold price** (what worked for Sweden):  
     `=IFERROR(Volume!<2023_volume_cell>*AVERAGEIF('Gold price'!$A:$A,"2023M*",'Gold price'!$B:$B),"")`
   - For Total Reserves (2023), use `INDEX+MATCH` with (a) a year row match and (b) a wildcard country header match over the **full** header range (don’t truncate to just the visible STEP 3 columns). Example pattern:  
     `=IFERROR(INDEX('Total Reserves'!$C:$P, MATCH(2023,'Total Reserves'!$A:$A,0), MATCH(C20&":*", 'Total Reserves'!$C$1:$P$1,0)),"")`
   - If a country’s 2023 total reserves is blank/missing, **exclude/delete** that country from the STEP 3 table (as done for Finland/Sweden).

6. **Exposure and RaR calculations: lock a single volatility convention to avoid double-/mis-scaling**
   - Treat the STEP 1 “3‑month annualized” (Answer row 5) as the volatility input for risk, and convert it to a decimal **once**:
     - percent-points ⇒ `vol_ann_dec = $C$5/100`
     - true % formatted decimal ⇒ `vol_ann_dec = $C$5`
   - Compute near-term (3‑month horizon) exposure consistently from the annualized vol:  
     `Exposure = GoldValue * z * vol_ann_dec * SQRT(3/12)`
   - Compute `RaR% = Exposure / TotalReserves * 100` (format per template).

7. **Verify formulas safely; assume recalc tooling may fail**
   - Avoid array-dependent “last value” formulas and keep zero Excel error outputs (`#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, `#NAME?`) by construction (`IF`, `IFERROR`, correct ranges).
   - If using `/skills/xlsx/recalc.py`, run it on a **backup copy** and only promote the result if it returns `total_errors: 0` **and** the file is still loadable by `openpyxl.load_workbook` (LibreOffice recalc may corrupt named styles).
   - If recalc fails, validate by checking that (a) the rolling windows are correct (last 3 vs last 12 returns) and (b) the annualization/horizon scaling is applied exactly once.

8. **Save to the required output path**
   - Write the final workbook to the exact required location (e.g., `/root/output/rar_result.xlsx`).

## Expected Result
A saved `.xlsx` that preserves the original template, contains only Excel-formula-based computations, uses the template’s intended volatility definition (windowing, STDEV variant, annualization), pulls latest vol values from the last price row (not from fragile “last numeric in vol column” logic), correctly converts any Volume-only countries to value using Jan–Sep 2023 average price, excludes countries missing 2023 Total Reserves from STEP 3, and produces correct Exposure and RaR% values.
