# External data timeboxing + ingest verification

Use this when a workbook build depends on one or more external datasets and you risk spending the whole run on retrieval/parsing.

## Procedure

1. **List required series and landing zones**
   - Make a small table: `source → series_id → frequency → years → target sheet+range`.

2. **Timebox each source**
   - Set a budget (e.g., 5–10 minutes) per source for the *first* workable extraction.
   - Stop early if you hit: 403/Access Denied, login/CAPTCHA, infinite redirects, very slow parsing.

3. **Branch: choose a fallback path (including modality switches)**

```python
import pandas as pd

# Inputs you fill in per task
primary = {"kind": "url", "path": "https://example.com/blocked"}
fallback = {"kind": "file", "path": "bulk_download.xls"}

# Modality hint: when endpoints are blocked/SSL-failing, switch to a browser/
# Playwright download/export path, then read the downloaded file locally.

def read_any(spec):
    if spec["kind"] == "url":
        return pd.read_excel(spec["path"])  # may raise
    if spec["kind"] == "file":
        return pd.read_excel(spec["path"])  # may raise
    raise ValueError("unknown kind")

try:
    df = read_any(primary)
except Exception:
    df = read_any(fallback)
```

- **Branch A (blocked/slow or SSL/API errors):** switch modality (browser/Playwright export/download) or use a bulk downloadable artifact; stop trying to “fix” the endpoint.
- **Branch B (works):** proceed immediately to filtering/reshaping needed columns.

4. **Extract minimally, then ingest immediately**
   - Filter to the needed keys first.
   - Select only necessary columns/years to reduce memory/time.
   - Ingest into the workbook’s target range *before* moving to the next source.

5. **Verification: download ≠ ingest (with corrective action)**

```python
from openpyxl import load_workbook

wb = load_workbook("output.xlsx")
ws = wb["Sheet1"]

# Verify a target range is not empty (sample a few cells)
sample = [ws.cell(row=r, column=2).value for r in range(2, 6)]
if all(v is None or v == "" for v in sample):
    # Corrective action: you likely pasted to the wrong sheet/range or wrote
    # to a different file; go back and re-check the target sheet name + range,
    # then repeat the paste/import step.
    raise AssertionError("ingest check failed: target cells still empty")
```

**If verification fails:** return to step 4 and ensure you are writing to the correct sheet/range on the deliverable workbook; then re-run this verification before any further external searching.
