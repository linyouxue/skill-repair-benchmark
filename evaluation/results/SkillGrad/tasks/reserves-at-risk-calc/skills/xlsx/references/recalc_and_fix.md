# Recalculate formulas with recalc.py and fix errors

Use this when you changed/added formulas (or need to trust formula outputs) and must ensure the workbook contains no Excel error values.

## Procedure (with branches)

```python
import json
import subprocess
from pathlib import Path

xlsx_path = Path(xlsx_path_str)

# Branch A: file missing -> go back and save/export first
if not xlsx_path.exists():
    raise FileNotFoundError(
        f"Cannot recalc because workbook does not exist: {xlsx_path}. "
        "Save/export to this exact path, then retry."
    )

# Run recalc
p = subprocess.run(
    ["python", "recalc.py", str(xlsx_path)],
    capture_output=True,
    text=True,
    check=True,
)
report = json.loads(p.stdout)

# Branch B: errors found -> locate, fix, and rerun
if report.get("status") == "errors_found":
    summary = report.get("error_summary", {})
    locations = []
    for err, meta in summary.items():
        locations.extend(meta.get("locations", []))

    # next corrective action: open workbook and fix the specific locations
    raise AssertionError(
        f"Excel errors detected: {summary}. "
        f"Fix these cell locations, save, and rerun recalc: {locations[:10]}"
    )

# Verification: require clean report
assert report.get("status") == "success" and report.get("total_errors", 0) == 0, report
```

## Verification and corrective action
- If the assertion fails because the file is missing: re-check the required output path/filename, save/export to that exact path, then rerun.
- If the assertion fails because errors were found: fix the listed cell locations (common fixes: correct references for #REF!, guard denominators for #DIV/0!, coerce types for #VALUE!), save, and rerun recalc until status=success.
