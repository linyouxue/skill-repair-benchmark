# Completion gate for template-based workbooks

Use this when the task expects many ranges/tabs to be populated and downstream formulas depend on upstream inputs.

## Inputs
- A list of **required ranges**: `(sheet_name, min_row, max_row, min_col, max_col)`.
- A list of **key cells** that must evaluate to numeric values (or at least be non-empty formulas).
- A list of **core formula sheets**: sheet names where formulas must exist in the model area.

## Gate algorithm (with branch)

```python
from openpyxl import load_workbook

required_ranges = [
    ("Sheet1", 2, 10, 1, 5),
]
key_cells = [
    ("Sheet1", "B2"),
]
core_formula_sheets = [
    "Sheet1",
]

wb = load_workbook("output.xlsx")

# Branch A: range emptiness checks
empty_ranges = []
for name, r1, r2, c1, c2 in required_ranges:
    ws = wb[name]
    values = [ws.cell(r, c).value for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
    if all(v is None or v == "" for v in values):
        empty_ranges.append((name, r1, r2, c1, c2))

# Branch B: formula presence check (workbook-wide)
formula_count = 0
for ws in wb.worksheets:
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                formula_count += 1

# Branch C: key-cell check
missing_keys = []
for sheet, addr in key_cells:
    v = wb[sheet][addr].value
    if v is None or v == "":
        missing_keys.append((sheet, addr))

# Branch D: per-core-sheet formula presence (template model tabs)
missing_formula_sheets = []
for name in core_formula_sheets:
    ws = wb[name]
    has_formula = any(
        isinstance(cell.value, str) and cell.value.startswith("=")
        for row in ws.iter_rows()
        for cell in row
    )
    if not has_formula:
        missing_formula_sheets.append(name)

if empty_ranges or formula_count == 0 or missing_keys or missing_formula_sheets:
    raise AssertionError({
        "empty_ranges": empty_ranges,
        "formula_count": formula_count,
        "missing_key_cells": missing_keys,
        "missing_formula_sheets": missing_formula_sheets,
    })
```

## Verification (what to do on failure)

1. **Re-run the gate on the *deliverable* file** you will submit (not the template, not an earlier checkpoint).
2. If `missing_formula_sheets` is non-empty: open those sheets and build at least one complete formula chain (landing inputs → linked cells → derived cells), then re-run the gate.
3. If `formula_count == 0`: you likely wrote to the wrong file/sheet or failed to enter formulas. Re-open the intended output workbook and write formulas as strings starting with `=`.
4. If `empty_ranges` is non-empty: stop external work; re-check sheet names and row/column offsets; then re-run the ingest/paste for those specific ranges.
5. If `missing_key_cells` is non-empty: trace dependencies backwards—confirm upstream inputs exist before re-writing downstream formulas.

After fixes, re-run the gate until it passes, then save/submit.
