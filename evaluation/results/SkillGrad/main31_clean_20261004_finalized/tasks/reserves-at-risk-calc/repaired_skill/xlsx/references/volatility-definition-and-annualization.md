# Volatility definition + annualization disambiguation

Use this when the workbook requests a volatility (e.g., “3M vol”) and an “annualized” version but does not explicitly specify:
- return type (log vs simple)
- estimator (sample vs population)
- time-step (daily vs monthly)
- what “3M” means (window length vs horizon)
- the annualization scaling

## Procedure (with runtime branches)

### 1) Inspect the template for a canonical definition
Look for any of:
- existing filled vol/annualized-vol cells on any sheet
- notes/legends near the table
- named ranges, helper rows, or prior-year examples
- a pair of cells where both non-annualized and annualized values are shown (best anchor)

### 2) Identify the time-step of returns used by the table
- If the input series is monthly levels and returns are computed month-over-month, the time-step is monthly.
- If the input series is daily prices, the time-step is daily.

### 3) Branch on what “3M vol” label implies

**Branch A — “3M vol” is a *monthly σ estimate* computed from a 3-month rolling window**
- Definition: `vol_3m = STDEV(<last 3 monthly returns>)` (or `STDEV.S` / `STDEV.P` per template)
- Annualize to 12 months: `vol_3m_ann = vol_3m * SQRT(12)`

**Branch B — “3M vol” is a *3-month-horizon* volatility**
- Definition: depends on template; a common approach is scaling the monthly σ to a 3-month horizon, then annualizing.
- If the template already defines a 3M horizon measure, annualize from 3 months to 12 months: `vol_3m_ann = vol_3m * SQRT(12/3)`

**Branch C — ambiguous**
Compute both candidates in helper cells and reconcile against template evidence (example value, or relationship to another horizon).

## Runnable Python snippet (write helper formulas + choose)

This example shows how to populate two competing annualizations and then select one once you identify which matches the template.

```python
from openpyxl import load_workbook

wb = load_workbook("input.xlsx", data_only=False)
ws = wb[wb.sheetnames[0]]

# Generic cell locations (replace with discovered ones during inspection)
vol_cell = "B2"           # where non-annualized 3M vol lives
ann_candidate_a = "C2"    # annualize as monthly σ -> √12
ann_candidate_b = "D2"    # annualize as 3M horizon -> √(12/3)
final_ann_cell = "E2"     # the template's required annualized output cell

# Candidate formulas (use the workbook's STDEV convention and return definition elsewhere)
ws[ann_candidate_a] = f"={vol_cell}*SQRT(12)"
ws[ann_candidate_b] = f"={vol_cell}*SQRT(12/3)"

# Branch: choose based on inspected evidence (set one of these flags after inspection)
use_a = True
use_b = False

if use_a and not use_b:
    ws[final_ann_cell] = f"={ann_candidate_a}"
elif use_b and not use_a:
    ws[final_ann_cell] = f"={ann_candidate_b}"
else:
    # Ambiguous: force a manual decision by leaving a visible marker
    ws[final_ann_cell] = '="CHECK_VOL_DEFINITION"'

wb.save("output.xlsx")
```

## Verification (and corrective action)

1) **Evidence match check:** confirm the chosen annualized value matches any template-provided example/anchor.
- If it does not match: switch branches (A ↔ B) and re-evaluate; if still mismatched, inspect return definition (log vs simple) and STDEV variant (S vs P).

2) **Sanity check across horizons:** if the workbook also has 6M/12M vol, the annualized vol should be plausible (not wildly larger/smaller) and should respect general scaling intuition (longer windows often smooth volatility).
- If sanity fails: re-check the return time-step (daily vs monthly) and annualization factor (√252 vs √12).

3) **Recalc check:** run `python3 recalc.py output.xlsx` and ensure `total_errors == 0`.
- If errors found: fix the specific cells/functions reported, then recalc again; do not replace formulas with constants.
