# Excel Solver / Goal Seek / Data Table setup

Trigger: the task names Excel Solver, Goal Seek, Data Table, or Scenario
Manager, or a step requires minimizing/maximizing an objective subject to
constraints that reference input cells.

Two failure modes this chapter prevents:

1. **Pre-solving in Python and pasting numbers with no wiring.** The
   workbook looks correct on first open but is hardcoded — the objective
   cell will not respond when an input changes, and the Solver wiring the
   grader expects to inspect is not present.
2. **Wiring the Solver cells correctly but shipping with the changing
   cells empty / at a trivial guess.** `wb.save` and `recalc.py` do NOT
   execute Excel Solver (it is a GUI feature). The workbook ships with
   changing cells at whatever Python wrote; the objective evaluates to a
   degenerate value, and the grader sees "Solver was never run".

The correct resolution writes BOTH the surrounding formula wiring AND a
numerical pre-fill of the changing cells.

## Required workbook structure

Three cell roles must exist as live Excel structures:

1. **Changing cells** — holds the numerical solve result (pre-filled in
   Phase A by a Python solve). Not a formula; a plain number. Comment
   the first cell: "Solver changing cell — pre-filled with numerical
   solve; headless pipeline does not execute Solver".
2. **Objective cell** — a live Excel formula whose value depends on the
   changing cells (directly or through intermediate formulas). Solver
   minimizes/maximizes this.
3. **Constraint / residual formulas** — live Excel formulas referencing
   the changing cells, not pre-evaluated numbers. These appear either as
   named constraint cells or inline inside the objective expression.

A human reviewer who re-runs Solver on this workbook gets the same (or
improved) answer. The grader sees the objective at a non-degenerate
numeric value on first open.

## Worked example — HP-filter-style penalized least squares

The HP filter minimizes `Σ (y - trend)² + λ Σ (Δ²trend)²` over the trend
series. Closed-form solution: `trend = (I + λ·Dᵀ·D)⁻¹ · y`, where `D` is
the second-difference operator. One `numpy.linalg.solve` call. The
surrounding Excel formulas remain live so a human can re-run Solver.

```python
import numpy as np
from openpyxl import load_workbook
from openpyxl.comments import Comment

wb = load_workbook(template_path)
ws = wb[target_sheet]

INPUT_COL   = "K"   # observed series y
TREND_COL   = "L"   # changing cells — Solver would minimize over these
SQERR_COL   = "M"   # (y - trend)^2
D2_COL      = "N"   # (trend_{t+1} - 2*trend_t + trend_{t-1})^2
FIRST, LAST = 6, 27
LAMBDA_CELL = "$P$3"
LAMBDA_VAL  = 100.0   # read from template if present; else task-stated

# 1. Numerical solve — closed-form penalized least squares
y = np.array([ws[f"{INPUT_COL}{r}"].value for r in range(FIRST, LAST + 1)],
             dtype=float)
n = len(y)
D = np.zeros((n - 2, n))
for i in range(n - 2):
    D[i, i], D[i, i + 1], D[i, i + 2] = 1.0, -2.0, 1.0
trend = np.linalg.solve(np.eye(n) + LAMBDA_VAL * D.T @ D, y)

# 2. Write changing cells with the numerical pre-fill (NOT a formula)
for i, r in enumerate(range(FIRST, LAST + 1)):
    ws[f"{TREND_COL}{r}"] = float(trend[i])
ws[f"{TREND_COL}{FIRST}"].comment = Comment(
    "Solver changing cell — pre-filled with numerical penalized-"
    "least-squares solve; headless pipeline does not execute Solver.",
    "solver",
)

# 3. Residual columns as LIVE formulas
for r in range(FIRST, LAST + 1):
    ws[f"{SQERR_COL}{r}"] = f"=({INPUT_COL}{r}-{TREND_COL}{r})^2"
    if FIRST < r < LAST:
        ws[f"{D2_COL}{r}"] = (
            f"=({TREND_COL}{r+1}-2*{TREND_COL}{r}+{TREND_COL}{r-1})^2"
        )

# 4. Objective cell as a LIVE formula over the two sums
ws["P5"] = (
    f"=SUM({SQERR_COL}{FIRST}:{SQERR_COL}{LAST})"
    f"+{LAMBDA_CELL}*SUM({D2_COL}{FIRST+1}:{D2_COL}{LAST-1})"
)
ws["P5"].comment = Comment(
    "Solver objective: minimize by changing "
    f"{TREND_COL}{FIRST}:{TREND_COL}{LAST}",
    "solver",
)

wb.save(output_path)
```

Why this is NOT the "pre-solve in Python" anti-pattern:

- The anti-pattern is hardcoding cells that COULD be live Excel formulas
  (sums, ratios, growth rates). Those cells have an obvious formula; the
  rule is "write the formula, not the result".
- Solver changing cells have NO formula of their own — they are inputs
  that an interactive Solver run would overwrite. In a headless pipeline
  Solver never runs; something must put values in those cells, or the
  objective is degenerate. The numerical pre-fill is the only option
  that leaves the surrounding model non-degenerate.

## Decision rule — did I wire it, or did I pre-solve the wrong thing?

Delete the Python script. Open the workbook. Change one input cell
(`K10`). Press F9 to recalc. Does the objective cell (`P5`) change?

- **Yes → wired correctly.** The changing cells hold numerical pre-fills
  (not formulas), the residuals/objective are live formulas, and a human
  can press Solver → Solve to re-minimize.
- **No → the surrounding formulas are hardcoded.** Rewrite the
  residuals / objective as formulas following the pattern above.

Then check the objective's current value:

- **Non-zero, non-error, finite → wiring + pre-fill both correct.**
- **Zero / `#N/A` / `None` → the changing cells are empty or at a
  trivial guess.** Compute the numerical solve and write the pre-fill.

## Branch — Goal Seek / Data Table / Scenario Manager

Same two-part pattern (formula wiring + numerical pre-fill of the
feature's target cell), different wiring:

- **Goal Seek**: the "set cell" is a live formula; the "by changing"
  cell gets a numerical pre-fill computed in Python (one-variable
  root-find — `scipy.optimize.brentq` or Newton).
- **Data Table**: the input column/row is a list of scenario values
  (hardcoded is fine — they are scenarios, not solve outputs); the
  result column/row references a single formula cell. Pre-fill each
  result cell by evaluating the formula in Python for each scenario
  input, since LibreOffice does not materialize Data Table outputs.
- **Scenario Manager**: each scenario stores values for the SAME set of
  input cells; downstream calculations are formulas, not pasted outputs.

In every case: the OUTPUT the feature would produce must ship with a
numerical value AND the downstream formulas must be live.

## Verification step

After saving and running `recalc.py`, re-open with `data_only=True` and
run three checks:

```python
from openpyxl import load_workbook

ERROR_STRINGS = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}

wb_val = load_workbook(output_path, data_only=True)
ws_val = wb_val[target_sheet]
wb_fml = load_workbook(output_path, data_only=False)
ws_fml = wb_fml[target_sheet]

# Check 1: every changing cell holds a finite numeric pre-fill.
for r in range(FIRST, LAST + 1):
    v = ws_val[f"{TREND_COL}{r}"].value
    assert isinstance(v, (int, float)) and v is not None, (
        f"{TREND_COL}{r}: changing cell is not a numerical pre-fill (got {v!r})"
    )

# Check 2: objective cell is a formula AND evaluates to a non-degenerate value.
obj_formula = ws_fml["P5"].value
obj_value   = ws_val["P5"].value
assert isinstance(obj_formula, str) and obj_formula.startswith("="), (
    "objective is not a formula"
)
assert isinstance(obj_value, (int, float)) and obj_value not in (None, 0), (
    f"objective evaluates to degenerate value {obj_value!r} — changing cells"
    " likely empty or at trivial guess"
)

# Check 3: perturb-and-recalc — change one input, re-run recalc.py,
# confirm the objective value moves. If it does not, an intermediate
# column (residuals, second differences) is itself hardcoded.
```

**On failure:**

- Check 1 fires → changing cells are empty, a formula, or an error.
  Compute the numerical solve (as in the worked example) and write a
  plain-number pre-fill into each changing cell. Re-run `recalc.py`.
- Check 2 fires on the formula part → the objective was written as a
  number. Replace with the `SUM(...) + λ·SUM(...)` formula referencing
  the live residual columns.
- Check 2 fires on the value part (formula correct, value degenerate)
  → the changing cells are empty / zeros / trivial guesses. Compute
  the numerical solve and write the pre-fill, then re-run `recalc.py`.
- Check 3 perturbation shows no movement → an intermediate column
  (residuals, second differences) was itself hardcoded. Walk the
  dependency chain from objective back to changing cells and rewrite
  each intermediate as a formula.
