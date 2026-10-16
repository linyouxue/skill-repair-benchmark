# Inventory a wide table (keys + units) before mapping

Use this procedure when the workbook’s logic depends on selecting the correct subset of columns/series (e.g., which countries have a given year populated) and/or converting between units based on per-series metadata.

## Goal
1) enumerate the *complete* key set implied by the data (not by the prompt), 2) capture unit metadata needed for conversions, 3) only then build formulas/links in the destination sheet.

## Procedure (with runtime branches)

```python
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
import re

wb = load_workbook("input.xlsx", data_only=False)
ws = wb[wb.sheetnames[0]]

header_row = 1
unit_row = 2          # may differ; detect if needed
target_year_row = 10  # the row holding the year of interest
first_data_col = 2
last_data_col = ws.max_column

def norm_key(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

present = []
for c in range(first_data_col, last_data_col + 1):
    v = ws.cell(row=target_year_row, column=c).value
    if v is None or v == "":
        continue
    hdr = norm_key(str(ws.cell(row=header_row, column=c).value))
    unit = norm_key(str(ws.cell(row=unit_row, column=c).value))
    present.append({"col": c, "col_letter": get_column_letter(c), "header": hdr, "unit": unit, "value": v})

# Branch A: nothing found -> you likely picked wrong year row / sheet
if not present:
    raise ValueError("No non-empty cells found; confirm sheet and target_year_row by inspecting the workbook.")

# Branch B: found candidates -> inspect unit consistency
units = {p["unit"] for p in present}
print("Found", len(present), "series; units:", units)
```

### Branch: unit row is unknown
If you don’t know where units live, locate it by scanning a few rows above the data row for strings containing unit-like tokens.

```python
unit_tokens = ("thousand", "million", "billion", "oz", "ounce", "troy", "kg", "ton", "usd", "local")

def looks_like_unit(x) -> bool:
    s = ("" if x is None else str(x)).lower()
    return any(t in s for t in unit_tokens)

candidate_rows = []
for r in range(max(1, target_year_row - 8), target_year_row):
    hit = sum(looks_like_unit(ws.cell(r, c).value) for c in range(first_data_col, last_data_col + 1))
    if hit:
        candidate_rows.append((r, hit))

# Branch A: no candidate unit row -> conversions must be treated as ambiguous
if not candidate_rows:
    unit_row = None
else:
    unit_row = max(candidate_rows, key=lambda t: t[1])[0]

print("unit_row=", unit_row)
```

## Translate units to a scale factor (example)
Map unit text to a multiplier that converts the stored number into a canonical unit.

```python
def unit_scale(unit_text: str) -> float | None:
    u = (unit_text or "").lower()
    if "thousand" in u:
        return 1e3
    if "million" in u:
        return 1e6
    if "billion" in u:
        return 1e9
    # Branch: unknown unit -> return None and force a decision
    return None

for p in present[:5]:
    p["scale"] = unit_scale(p["unit"])

unknown = [p for p in present if p.get("scale") is None]
if unknown:
    print("Unknown unit for columns:", [(p["col_letter"], p["header"], p["unit"]) for p in unknown])
```

## Verification (and corrective action)
1. **Key-set verification:** confirm that the number of discovered series matches what you see by manually checking the target year row across the sheet.
   - If mismatch: adjust `target_year_row`, `first_data_col`, and the sheet selection; re-run inventory.
2. **Unit verification:** for every series you will convert, `scale` must be non-`None` and the unit must be compatible with the conversion.
   - If any unknown/ambiguous unit: **do not assume**; either (a) locate the correct unit row and re-run, or (b) exclude/flag those series in the destination until clarified.
3. **Mapping verification:** after writing destination formulas, run `python recalc.py output.xlsx` and ensure `total_errors == 0`.
   - If errors found: fix the specific references/functions listed and re-run recalc; never “fix” by replacing formulas with constants.
