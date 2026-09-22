---
name: xlsx
description: Create, edit, and validate spreadsheet deliverables with pandas/openpyxl, including strict output contracts, formula safety, and post-write verification.
license: Proprietary. LICENSE.txt has complete terms
---

# XLSX creation, editing, and analysis

## Deliverable-first control loop (prevent tool-call wandering)

When the task is graded on a saved workbook, treat the workbook as the primary objective and drive the run in a straight line: plan once → produce → validate. If upstream extraction/OCR/parsing is incomplete, still create the workbook with best-effort values (including nulls) and then iterate on filling it.

1. Restate the output contract (exact path, sheet names, required columns/order, row ordering/uniqueness constraints).
2. Create a minimal skeleton workbook early (headers + empty rows if needed).
3. Batch upstream work (e.g., OCR/parse) without interleaving unrelated exploration.
4. Populate rows; prefer deterministic parsing rules over ad-hoc retries.
5. Save to the exact required path (treat it as an absolute contract path, not a “nearby” directory).
6. Re-open and validate (existence at the contract path, sheets, headers/order, required constraints).
7. If validation fails, fix the workbook and re-export before doing more upstream work.

```python
from pathlib import Path
import pandas as pd

contract_path = "/path/to/output.xlsx"
out_path = Path(contract_path)
out_path.parent.mkdir(parents=True, exist_ok=True)

required_sheet = "results"
required_cols = ["col_a", "col_b", "col_c"]

df = pd.DataFrame(rows, columns=required_cols)
df.to_excel(out_path, index=False, sheet_name=required_sheet)

assert out_path.exists(), f"Missing deliverable at contract path: {out_path}"
check = pd.read_excel(out_path, sheet_name=required_sheet)
assert list(check.columns) == required_cols
```

Decision rule: if you have made several tool calls without creating the deliverable file, stop exploring and immediately write the skeleton workbook, then proceed.

Hard trigger: after ~3 tool calls (or once you know the contract), you must have saved a skeleton workbook to the exact required path and re-opened it to confirm it exists and the schema matches; do not end the run until the re-open checks pass.

### Termination guardrail (must pass before `end_turn`)
Before ending the run, ensure these statements are true for the required output path:
- The file exists at the exact contract path (check `Path(contract_path).exists()`).
- You did not substitute a relative/alternate path (use the contract string as the save target).
- Re-opened sheet set matches exactly (including order/count).
- Header names and order match exactly.

If any is false, do not `end_turn`: rewrite the workbook to the exact contract path, then re-open/validate again.

Read references/output-contract-excel.md when the task specifies an exact output path, sheet name(s), or strict column/order requirements for the delivered workbook. Skip when you are only exploring data interactively and no file deliverable will be graded.

## Requirements for outputs

### All Excel files: zero formula errors
- Every Excel model MUST be delivered with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)

### Preserve existing templates (when updating templates)
- Study and EXACTLY match existing format, style, and conventions when modifying files
- Never impose standardized formatting on files with established patterns
- Existing template conventions ALWAYS override these guidelines

## Reading and analyzing data (pandas)

Use pandas for bulk I/O and data shaping; use openpyxl when you must preserve formatting or author formulas.

```python
import pandas as pd

df = pd.read_excel("input.xlsx")
summary = df.groupby("group_col", dropna=False).size().reset_index(name="n")
summary.to_excel("output.xlsx", index=False)
```

## Editing / authoring with formulas (openpyxl)

Prefer formulas in the workbook over hardcoded computed values so the file stays dynamic.

```python
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.append(["x", "y", "sum"])
ws.append([1, 2, "=A2+B2"])
ws.append([3, 4, "=A3+B3"])
wb.save("output.xlsx")
```

Decision rule: if the deliverable is a flat table with no formulas/formatting requirements, use pandas; otherwise use openpyxl.

## Recalculating formulas (LibreOffice)

Workbooks written by openpyxl store formulas but may not store calculated values; run the provided recalculation step when formulas matter.

```bash
python recalc.py output.xlsx
```

## Common pitfalls

- Finishing upstream work (OCR/parsing/analysis) but never writing the required workbook to the exact contract path.
- Writing a workbook but not re-opening it to confirm existence at the contract path plus sheet names and header order.
- Saving to a “nearby” relative path (e.g., under the current working directory) instead of the mandated absolute contract path.
- Saving with `data_only=True` and accidentally overwriting formulas with values.
- Hardcoding computed numbers in Python when the spreadsheet should contain formulas.
- Ignoring formula error scans; fix the referenced cells/ranges and re-run recalculation.
