# Post-write verification for delivered .xlsx artifacts

Use this when the evaluator likely checks *the saved workbook* for strict invariants (sheet names, headers, row order/count, and cell values), or when you iterated on logic and want to ensure you didn’t save an earlier version.

## Procedure (branched)

### Branch A — single-sheet, strict-schema deliverable (common in benchmarks)

```python
from pathlib import Path
import pandas as pd

out_path = Path("output.xlsx")
expected_sheet = "results"
expected_columns = ["col1", "col2", "col3"]

# 1) Existence + non-empty
assert out_path.exists(), f"missing output: {out_path}"
assert out_path.stat().st_size > 0, f"empty output: {out_path}"

# 2) Sheet set and schema
sheets = pd.read_excel(out_path, sheet_name=None)
assert list(sheets.keys()) == [expected_sheet], f"unexpected sheets: {list(sheets.keys())}"

df = sheets[expected_sheet]
assert list(df.columns) == expected_columns, f"bad header: {list(df.columns)}"

# 3) Row-count + ordering invariants
assert len(df) > 0, "no data rows"
if "col1" in df.columns:
    assert df["col1"].is_monotonic_increasing, "ordering invariant failed"

# 4) Semantic anomaly scan gate (required when values come from heuristics)
# Treat prompt exclusions as assertions, not as "scoring hints".
if {"total_amount", "date"}.issubset(df.columns):
    excl = r"\b(gst|sst|vat|tax)\b"
    src = df.get("source_text", pd.Series([""] * len(df))).astype(str).str.lower()

    bad_total_context = src.str.contains(excl, regex=True) & df["total_amount"].notna()
    bad_date = ~pd.to_datetime(df["date"], errors="coerce").notna() & df["date"].notna()

    flagged = df[bad_total_context | bad_date]
    assert len(flagged) == 0, (
        "semantic verification failed: rows violate exclusions or have invalid dates; "
        "inspect flagged rows against OCR snippets, tighten extraction rules, re-write, and re-verify"
    )
```

Runtime branch: if you do not have a `source_text`/provenance column, create one during extraction (e.g., store the matched OCR line + neighbors) so you can audit excluded contexts and re-run deterministically.

### Branch B — multi-sheet workbooks (template-like outputs)

```python
from pathlib import Path
from openpyxl import load_workbook

out_path = Path("output.xlsx")
required_sheets = {"Inputs", "Model", "Outputs"}

assert out_path.exists() and out_path.stat().st_size > 0

wb = load_workbook(out_path, data_only=False)
actual = set(wb.sheetnames)
assert required_sheets.issubset(actual), f"missing sheets: {required_sheets-actual}"

ws = wb["Outputs"]
assert ws.max_row >= 2, "no output rows"
```

Runtime branch: if formulas must be evaluated for grading, run `recalc.py` first and then re-open with `data_only=True` to check displayed values.

## Verification and corrective action

- If **any assertion fails**: do **not** declare completion. Fix the writer (sheet name, header, sorting, filtering, formula references) and/or extraction logic, re-write the file, and re-run this verification from the top.
- If semantic checks fail due to heuristic extraction: print the flagged rows, show their provenance snippets, tighten absolute exclusions / null-on-ambiguity thresholds, then re-run extraction end-to-end.
- If the file exists but appears to reflect an **earlier logic version**: add a deterministic “build id” marker (e.g., a timestamp cell or a hash printed to logs) *during* the write step, then confirm it appears in the re-opened workbook before finalizing.
