---
name: xlsx
description: Create, edit, and analyze .xlsx files (often from a provided template)
  using Excel formulas for all computations, with unit-consistent finance math (returns/volatility/VaR-style
  exposure), robust lookups, and safe verification/recalculation.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. **Open and inspect the workbook/template before writing anything**
   - Load with `openpyxl.load_workbook(..., data_only=False)` and identify the exact input columns/rows and any pre-existing conventions.
   - **Preserve the template exactly** (layout, headers, styles, existing formulas). Template conventions override any generic standards.
   - Keep standard model conventions when the template is silent: blue = inputs, black = formulas, green = internal links, red = external links; keep consistent number formats (currency, %, negatives in parentheses, etc.).
   - Never save a workbook you opened with `data_only=True` (it can overwrite formulas with values).

2. **Bring in source data (values only) without assuming fixed row counts**
   - Use pandas to read external workbooks for extraction, but write the extracted series into Excel as raw values in the template’s expected locations.
   - Detect the last row of pasted data and base formula fill ranges on that (don’t hardcode “row 14” / “last row”).

3. **Do all computations in Excel formulas (no hardcoded calculated outputs) and keep units explicit**
   - Decide whether returns/vols are **percent** or **decimal** up front and keep it consistent end-to-end.
   - For monthly log returns expressed as **percent** (per the hint), use:
     - `=IF(OR(curr_price="",prev_price=""),"",LN(curr_price/prev_price)*100)`
   - Build rolling volatility off the **same return units**:
     - **3‑month volatility (trailing 3 monthly log returns, in %):** `=IF(Crow="","",STDEV.S(Crow-2:Crow))`
     - **12‑month volatility (annualized from trailing 12 monthly log returns, in %):** `=IF(Crow="","",STDEV.S(Crow-11:Crow)*SQRT(12))`
   - Fill formulas down through the true last data row; ensure early rows return blank (not `#DIV/0!`, `#VALUE!`, etc.).

4. **Populate “Answer” cells using dynamic references to the latest computed data**
   - For the 95% one-sided z-score, use the proven formula: `=NORMSINV(0.95)`.
   - When the instruction says “use the latest data”, pull the **last nonblank** volatility value (avoid fixed coordinates like `D14`):
     - Example pattern: `=LOOKUP(2,1/('Gold price'!D:D<>""),'Gold price'!D:D)`
   - For “3‑month annualized”, annualize from the 3‑month volatility you pulled:
     - If 3‑month volatility is in **monthly %**, annualized = `=C4*SQRT(12)`.

5. **Use robust country/year lookups (keep what worked)**
   - Pull 2023 gold reserve **values** directly from the `Value` sheet via links/lookup formulas (don’t retype).
   - For Total Reserves 2023, use `INDEX+MATCH` or `XLOOKUP`; if the year is a header, match it robustly (what worked):
     - Example header match: `MATCH("*2023*", header_row_range, 0)`
   - Prevent Excel error outputs: use `IFERROR(…, "")` where appropriate, and if the instructions say to delete countries missing 2023 Total Reserves, **remove them** rather than leaving `#N/A`.

6. **Exposure and RaR calculations: apply horizon + percent/decimal scaling correctly**
   - Convert percent vol to decimal **once** in risk math: `vol_decimal = vol_percent/100`.
   - For a **near-term (3‑month) valuation swing**, scale an annualized volatility to a 3‑month horizon:
     - `Exposure = GoldValue * z * (Vol_annualized/100) * SQRT(3/12)`
   - Compute RaR% from the STEP 3 table values:
     - `RaR% = Exposure / TotalReserves * 100` (format as % per template).

7. **Verify formulas safely; don’t let recalculation tooling corrupt the deliverable**
   - Keep **zero Excel error values** (`#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, `#NAME?`) by construction (`IF`, `IFERROR`, correct ranges).
   - If using `/skills/xlsx/recalc.py`, run it on a **backup copy** of the file and only promote the result if it returns success with `total_errors: 0`.
   - If recalc tooling fails in-environment, fall back to: (a) checking formula strings/ranges/units, and (b) computing a few spot-check values in Python **only for validation** (do not write those numbers back as hardcodes).

8. **Save to the required output path**
   - Write the final workbook to the exact required location (e.g., `/root/output/rar_result.xlsx`).

## Expected Result
A saved `.xlsx` that preserves the original template, contains only Excel-formula-based computations, has zero Excel error outputs, correctly computes log returns (×100), rolling volatilities and annualization, applies correct horizon scaling for near-term exposure, and produces consistent Exposure and RaR% values.
