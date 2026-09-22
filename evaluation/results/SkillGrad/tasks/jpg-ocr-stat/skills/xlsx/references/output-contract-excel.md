# Output contract for Excel deliverables (save + re-open validation)

## When to use
Use this procedure when a task is graded on a delivered `.xlsx` file and specifies any of:
- an exact output path
- required sheet name(s) or sheet count
- required columns (names, order, casing)
- required row ordering (e.g., sort by a key) or uniqueness constraints

Skip when you are only returning data in-chat and no workbook artifact is required.

## Procedure

### 1) Write the workbook deterministically
- Create the parent directory.
- Write exactly the required sheets.
- Write exactly the required columns in the required order.

```python
from pathlib import Path
import pandas as pd

out_path = Path("/path/to/output.xlsx")
out_path.parent.mkdir(parents=True, exist_ok=True)

required_sheet = "results"
required_cols = ["col_a", "col_b", "col_c"]

df = pd.DataFrame(rows)[required_cols]

with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name=required_sheet)
```

### 2) Re-open and validate (runtime branch)
Validate existence, sheet set, and header equality. Branch depending on what fails.

```python
from pathlib import Path
import pandas as pd

out_path = Path("/path/to/output.xlsx")
required_sheet = "results"
required_cols = ["col_a", "col_b", "col_c"]

if not out_path.exists():
    raise FileNotFoundError(f"Missing deliverable: {out_path}")

sheets = pd.ExcelFile(out_path).sheet_names
if sheets != [required_sheet]:
    raise ValueError(f"Unexpected sheets: {sheets} (expected only {required_sheet})")

check = pd.read_excel(out_path, sheet_name=required_sheet)
if list(check.columns) != required_cols:
    raise ValueError(f"Header mismatch: {list(check.columns)} != {required_cols}")
```

### 3) Verify ordering / uniqueness constraints
If the task requires ordering or uniqueness, assert it explicitly.

```python
key = "col_a"

if not check[key].is_unique:
    dup = check[key][check[key].duplicated()].head(10).tolist()
    raise ValueError(f"Non-unique key values (sample): {dup}")

if check[key].tolist() != sorted(check[key].tolist()):
    raise ValueError(f"Rows are not sorted by {key}")
```

## Verification and corrective action

- If the file is missing: re-run the export step and ensure you saved to the exact required path (not a nearby directory).
- If sheets are wrong: rewrite using `ExcelWriter` and only create the required sheet(s); remove extras.
- If headers are wrong: reorder/select columns explicitly (`df = df[required_cols]`) and rewrite.
- If ordering/uniqueness fails: fix upstream (sort/drop duplicates/aggregate as required), then rewrite and re-validate.

Only conclude the run after the re-open checks pass.
