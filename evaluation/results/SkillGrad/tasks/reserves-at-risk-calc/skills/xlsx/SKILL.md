---
name: xlsx
description: "Create, edit, analyze, and deliver spreadsheet artifacts with correct formulas, formatting, and verification, ensuring the final workbook is saved to the required output path."
license: Proprietary. LICENSE.txt has complete terms
---

# Requirements for Outputs

## All Excel files

### Zero Formula Errors
- Every Excel model MUST be delivered with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)

### Preserve Existing Templates (when updating templates)
- Study and EXACTLY match existing format, style, and conventions when modifying files
- Never impose standardized formatting on files with established patterns
- Existing template conventions ALWAYS override these guidelines

## Financial models

### Color Coding Standards
Unless otherwise stated by the user or existing template

#### Industry-Standard Color Conventions
- **Blue text (RGB: 0,0,255)**: Hardcoded inputs, and numbers users will change for scenarios
- **Black text (RGB: 0,0,0)**: ALL formulas and calculations
- **Green text (RGB: 0,128,0)**: Links pulling from other worksheets within same workbook
- **Red text (RGB: 255,0,0)**: External links to other files
- **Yellow background (RGB: 255,255,0)**: Key assumptions needing attention or cells that need to be updated

### Number Formatting Standards

#### Required Format Rules
- **Years**: Format as text strings (e.g., "2024" not "2,024")
- **Currency**: Use $#,##0 format; ALWAYS specify units in headers ("Revenue ($mm)")
- **Zeros**: Use number formatting to make all zeros "-", including percentages (e.g., "$#,##0;($#,##0);-")
- **Percentages**: Default to 0.0% format (one decimal)
- **Multiples**: Format as 0.0x for valuation multiples (EV/EBITDA, P/E)
- **Negative numbers**: Use parentheses (123) not minus -123

### Formula Construction Rules

#### Assumptions Placement
- Place ALL assumptions (growth rates, margins, multiples, etc.) in separate assumption cells
- Use cell references instead of hardcoded values in formulas
- Example: Use =B5*(1+$B$6) instead of =B5*1.05

#### Formula Error Prevention
- Verify all cell references are correct
- Check for off-by-one errors in ranges
- Ensure consistent formulas across all projection periods
- Test with edge cases (zero values, negative numbers)
- Verify no unintended circular references

#### Documentation Requirements for Hardcodes
- Comment or in cells beside (if end of table). Format: "Source: [System/Document], [Date], [Specific Reference], [URL if applicable]"

# XLSX creation, editing, and analysis

## Workflow: Deliver the required artifact (mandatory)
1. Extract and record the *exact* required deliverable type and *exact absolute* output path/filename from the task instructions.
2. Make edits/calculations in a working copy (in memory or on disk), but do not consider the task “done” yet.
3. Create the required output directory (parent folders) so saving cannot fail due to missing dirs.
4. Perform an explicit Save As/export to the required absolute output path/filename; do not leave the final deliverable under a convenient workspace-relative path unless the task explicitly requires it.
5. Immediately verify persistence by checking the file exists at the required path (optionally re-open it to ensure it is the final edited workbook).
6. If the file is missing or the name/path mismatches, treat this as a stop-the-world failure: correct the path/name and repeat steps 3–5 until verification passes.

```python
from pathlib import Path

required_out = Path(required_output_path_str)  # exact path+filename from task
required_out.parent.mkdir(parents=True, exist_ok=True)

wb.save(required_out)  # Save As / export to the mandated location

if not required_out.exists():
    raise FileNotFoundError(f"Output not written to required path: {required_out}")
```

Decision rule: treat “artifact exists at the exact required path/filename” as a completion gate; do not terminate before it passes (even if a working copy exists elsewhere).

## Workflow: Evidence discovery is root-scoped (diagnosis)
When determining what went wrong in an evaluation run, only use evidence paths under the allowed project root; never jump to absolute paths you “expect” the harness to have.

```python
from pathlib import Path

def find_first_existing(root_dir: str, rel_candidates: list[str]) -> Path | None:
    root = Path(root_dir)
    for rel in rel_candidates:
        p = root / rel
        if p.exists():
            return p
    return None
```

Decision rule: if expected verifier evidence is missing, enumerate plausible in-root alternatives before concluding a spreadsheet mistake.

Read references/evidence_discovery_root_scoped.md when verifier evidence is missing/unreadable or you see “escapes the allowed project root”. Skip when you already have readable in-root verifier artifacts that name the first failing check.

## Reading and analyzing data

### Data analysis with pandas
For data analysis, visualization, and basic operations, use pandas.

```python
import pandas as pd

df = pd.read_excel(input_path)
summary = df.describe(include="all")
df.to_excel(output_path, index=False)
```

## CRITICAL: Use formulas, not hardcoded values
Always put calculations in Excel formulas rather than computing in Python and pasting values, unless the task explicitly asks for static values.

```python
from openpyxl import load_workbook

wb = load_workbook(input_path)
ws = wb.active
ws["B2"] = "=SUM(B3:B10)"
wb.save(output_path)
```

## Recalculate formulas and scan for errors
If you added/changed formulas, run a recalculation and error scan before final delivery.

```python
import subprocess, json

p = subprocess.run(["python", "recalc.py", str(path_to_xlsx)], capture_output=True, text=True, check=True)
report = json.loads(p.stdout)
assert report["status"] == "success", report
```

Read references/recalc_and_fix.md when recalc.py reports errors_found or when formula results must be trusted. Skip when you did not introduce formulas and the workbook already contains correct cached values.

## Common Pitfalls
- Ending the run without saving/exporting the required workbook to the exact output path/filename (gate completion on an existence check against the required path, not a working path).
- Saving the final deliverable to a convenient workspace-relative path (e.g., under a local data/ directory) when the task requires a specific absolute output path.
- Overwriting formulas by loading with data_only=True and then saving.
- Hardcoding computed numbers in cells when a formula is required for a dynamic model.
- Assuming formulas are evaluated by openpyxl; always recalc when formula outputs matter.
