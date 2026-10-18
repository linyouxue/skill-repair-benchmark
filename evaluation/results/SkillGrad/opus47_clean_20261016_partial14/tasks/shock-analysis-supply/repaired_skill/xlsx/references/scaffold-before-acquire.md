# Scaffold the workbook BEFORE acquiring live data

Trigger: the task has two orthogonal workstreams — (A) writing an Excel
model (formulas, links, Solver wiring, table structure, downstream
calculations) that is NETWORK-INDEPENDENT, and (B) acquiring raw inputs
over the network. Read this BEFORE composing the first fetch call,
even if `time-boxed-acquisition.md` also applies.

The failure mode this chapter prevents: the executor serializes the two
workstreams as "acquire first, then model". When acquisition blocks (bot
challenges, 404s, late-install hangs), nothing gets written at all —
every formula, every link, every Solver cell is still blank at
`max_iterations`. A workbook with every formula wired and only raw-data
cells `=NA()` scores far higher than a workbook with one raw column
populated and everything else untouched.

## The two-phase invariant

- **Phase A — scaffold (offline).** Open the template, inspect every
  sheet, and write every formula, every cross-sheet link, every
  Solver changing-cell numerical pre-fill, every Solver
  objective/constraint formula, every table header, and every
  downstream calculation that does not depend on a raw-source value.
  Where a raw input would land, write `=NA()` (or leave the cell blank
  with a `pending:` comment). Save; verify mtime changed; verify the
  formula count meets the minimum derivable from the template.
- **Phase B — acquire (online).** Fetch raw inputs under the per-source
  time-box discipline in `time-boxed-acquisition.md`. Each landed source
  overwrites its `=NA()` placeholders.

Phase A must complete BEFORE the first fetch. If an executor is already
mid-Phase-B when it reads this chapter, Phase A has slipped — the
corrective action is to stop acquisition and return to Phase A.

## Step 0 — Enumerate Phase-A deliverables from template inspection

Template inspection (`template-inspection.md`) does not stop at
"recorded the headers". Its OUTPUT is a scaffold write list: every
non-raw cell addressed by coordinate, with the formula or placeholder
or Solver pre-fill that will be written there.

```python
# Build the scaffold write list from the inspected template
scaffold = []  # list of (sheet, coord, value_or_formula, kind)

# Entry kinds and what each is:
# "formula"              — live Excel formula computed by recalc.py
# "link"                 — cross-sheet reference formula
# "raw_placeholder"      — =NA() where a raw input will land in Phase B
# "solver_prefill"       — plain numerical value, pre-filled Solver changing cell
# "solver_objective"     — live SUM/SUMPRODUCT formula depending on changing cells
# "solver_constraint"    — live residual/constraint formula referencing changing cells
# "table_header"         — static label/header string

MIN_FORMULA_COUNT = sum(1 for s in scaffold
                        if s[3] in {"formula", "link",
                                    "solver_objective", "solver_constraint"})
```

## Step 1 — Write Phase A before any fetch

```python
import os
from openpyxl import load_workbook
from openpyxl.comments import Comment

PRE_TASK_MTIME = os.path.getmtime(output_path)

wb = load_workbook(output_path)
for sheet, coord, value, kind in scaffold:
    ws = wb[sheet]
    ws[coord] = value
    if kind == "raw_placeholder":
        ws[coord].comment = Comment("pending: raw input, Phase B", "scaffold")
    elif kind == "solver_prefill":
        ws[coord].comment = Comment(
            "Solver changing cell — pre-filled with numerical solve; "
            "headless pipeline does not execute Solver", "scaffold"
        )
wb.save(output_path)

assert os.path.getmtime(output_path) != PRE_TASK_MTIME, (
    "Phase A save did not change file mtime"
)
```

## Step 2 — The ~1/3-budget scaffold-complete invariant

At `ITER_BUDGET // 3` (e.g. iter 20 of 60), the workbook must hold
every Phase-A cell. This is a MECHANICAL gate executed as code — not
a prose target.

```python
ITER_BUDGET          = 60
SCAFFOLD_DEADLINE    = ITER_BUDGET // 3        # ~iter 20 of 60

def phase_a_complete(iter_counter, output_path, min_formula_count):
    if iter_counter < SCAFFOLD_DEADLINE:
        return "IN_PROGRESS"
    wb = load_workbook(output_path)
    actual = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    actual += 1
    if actual >= min_formula_count:
        return "COMPLETE"
    return "DEADLINE_MISSED"

# At iter SCAFFOLD_DEADLINE, call it:
status = phase_a_complete(iter_counter, output_path, MIN_FORMULA_COUNT)
```

### Branch — `phase_a_complete` returns `DEADLINE_MISSED`

Phase A has slipped past the 1/3 deadline. Corrective action:

1. STOP any in-flight acquisition work (no more fetches, no more
   `playwright install`, no more header variations).
2. Finish the scaffold write list from Step 0 against the current
   workbook state. Every missing formula / link / Solver pre-fill /
   Solver objective / Solver constraint / table row gets written now,
   with `=NA()` where a raw input is still outstanding.
3. Save, re-run `phase_a_complete`. Only once it returns `COMPLETE`
   may acquisition resume.

### Branch — `phase_a_complete` returns `COMPLETE`

Phase A is done. Proceed to Phase B under `time-boxed-acquisition.md`.
Each landed source overwrites the `=NA()` placeholders in its target
cells; the formula count only grows from here.

## Step 3 — Overwrite placeholders in Phase B

When a raw source lands in Phase B, open the workbook, overwrite the
`=NA()` cells with the raw values (keeping provenance comments per
`live-data-acquisition.md`), and save. Formulas depending on those
cells automatically recalculate on `recalc.py`.

```python
def flush_raw(sheet, coord_to_value, source_label):
    wb = load_workbook(output_path)
    ws = wb[sheet]
    for coord, value in coord_to_value.items():
        ws[coord] = value               # overwrites =NA() placeholder
        if ws[coord].comment is None or "pending" in ws[coord].comment.text:
            ws[coord].comment = Comment(f"Source: {source_label}",
                                        "acquisition")
    wb.save(output_path)
```

## Worked example — a model combining four scaffold-entry kinds

A typical "model from online data" task mixes four patterns. All of them
belong in Phase A; none require network. The example below shows how
each kind maps to a scaffold entry — adapt coordinates to the specific
template.

```python
scaffold = []

# Pattern 1: parameter formula computed from a global assumption cell
#   (e.g. a periodic depreciation rate derived from an average rate +
#    period input in named/anchor cells)
scaffold.append(
    ("Model", "B3",
     "=1-(1-avg_rate_cell)^(1/period_cell)",
     "formula")
)

# Pattern 2: link columns from a raw-data sheet (same raw-data cells may
#   still be =NA() placeholders until Phase B lands)
for i, src_row in enumerate(range(2, 24), start=0):
    tgt_row = 6 + i
    scaffold.append(
        ("Model", f"D{tgt_row}",
         f"=RawData!B{src_row}",
         "link")
    )

# Pattern 3: Solver-driven smoothing block (penalized least squares /
#   HP-filter / any convex objective)
import numpy as np
y = np.array(observed_series_or_zeros, dtype=float)
n = len(y)
D = np.zeros((n - 2, n))
for i in range(n - 2):
    D[i, i], D[i, i + 1], D[i, i + 2] = 1.0, -2.0, 1.0
trend_prefill = np.linalg.solve(np.eye(n) + lambda_val * D.T @ D, y)

for i, r in enumerate(range(6, 28)):
    scaffold.append(("Model", f"L{r}", float(trend_prefill[i]),
                     "solver_prefill"))
    scaffold.append(("Model", f"M{r}", f"=(K{r}-L{r})^2",
                     "solver_constraint"))
    if 6 < r < 27:
        scaffold.append(("Model", f"N{r}", f"=(L{r+1}-2*L{r}+L{r-1})^2",
                         "solver_constraint"))

scaffold.append(
    ("Model", "P5",
     "=SUM(M6:M27)+$P$3*SUM(N7:N26)",
     "solver_objective")
)

# Pattern 4: downstream calibration/production table — rows of formulas
#   that reference the trend cells and raw cells. These are the cells
#   the grader most often checks; they must be formulas, not blanks.
for r in range(36, 58):
    scaffold.append(("Model", f"B{r}",
                     f"=LN(L{r - 30})", "formula"))      # LnK example
    scaffold.append(("Model", f"C{r}",
                     f"=LN(D{r - 30})", "formula"))      # LnY example
scaffold.append(("Model", "E60", "=SLOPE(C36:C57,B36:B57)", "formula"))
scaffold.append(("Model", "F60", "=INTERCEPT(C36:C57,B36:B57)", "formula"))
```

Every one of these entries writes with zero network calls, in a single
`wb.save` at the end of Phase A. The raw cells on the `RawData` sheet
are still `=NA()` at this point; Phase B will overwrite them.

## Verification step

After declaring Phase A complete, assert both the formula count AND
that no downstream cell is itself a numeric hardcode where it should
be a formula. The grader rewards structural completeness, and a
numeric hardcode in a cell that should be a formula is a Phase-A
failure even if it currently shows the right value. Solver changing
cells are an explicit EXCEPTION — they are expected to be numerical
pre-fills.

```python
wb = load_workbook(output_path)
formulas_written = 0
suspicious_hardcodes = []
EXPECTED_FORMULA_CELLS = {           # populate from the scaffold list
    (sheet, coord) for (sheet, coord, _, kind) in scaffold
    if kind in {"formula", "link", "solver_objective", "solver_constraint"}
}
SOLVER_PREFILL_CELLS = {
    (sheet, coord) for (sheet, coord, _, kind) in scaffold
    if kind == "solver_prefill"
}
for sheet, coord in EXPECTED_FORMULA_CELLS:
    v = wb[sheet][coord].value
    if isinstance(v, str) and v.startswith("="):
        formulas_written += 1
    else:
        suspicious_hardcodes.append((sheet, coord, v))

assert formulas_written >= len(EXPECTED_FORMULA_CELLS), (
    f"Phase A incomplete: {formulas_written}/{len(EXPECTED_FORMULA_CELLS)} "
    f"expected formulas written"
)
assert not suspicious_hardcodes, (
    f"Phase A violation — cells that should be formulas hold hardcodes: "
    f"{suspicious_hardcodes[:5]}"
)
# Solver pre-fills must exist as finite numbers, NOT as formulas or None
for sheet, coord in SOLVER_PREFILL_CELLS:
    v = wb[sheet][coord].value
    assert isinstance(v, (int, float)) and v is not None, (
        f"Solver pre-fill {sheet}!{coord} is {v!r}; compute numerical "
        f"solve and write a plain number"
    )
```

**On failure:**

- Formula-count assertion fires → re-run Step 1 against the missing
  entries in the scaffold list. Do NOT begin or resume acquisition
  until this assertion passes.
- Hardcode assertion fires → for each listed cell, replace the
  hardcoded value with the formula from the scaffold write list; if
  the raw input it depends on has not yet landed, write `=NA()` and a
  `pending:` comment instead of a numeric placeholder.
- Solver-pre-fill assertion fires → the Solver changing cells were
  left as `=NA()` or formulas. Compute the numerical solve (see
  `excel-solver-setup.md` for the closed-form pattern) and write
  plain-number pre-fills; the surrounding objective/constraint
  formulas stay as live formulas.
