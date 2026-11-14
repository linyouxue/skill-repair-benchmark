---
name: xlsx
description: "Spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, strict-schema outputs, and formula recalculation."
license: Proprietary. LICENSE.txt has complete terms
---

# Requirements for Outputs

## All Excel files
- Deliver with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?).
- When editing an existing template, match its format, style, and conventions exactly.

## Strict-Schema Outputs (graded line-by-line)

Many tasks specify an exact output contract: a single sheet with a specific name, a fixed column set and order, deterministic row ordering, specific string formatting for numeric fields, and real nulls for missing values. These contracts are compared cell-by-cell against an oracle file, so any drift fails.

### Contract Checklist
- [ ] File written to the **exact** path the task specifies.
- [ ] Exactly one worksheet, with the **exact** name (case and spacing preserved, e.g., `results` not `Results` or `Sheet1`).
- [ ] Columns are exactly those requested, in the requested order, with the requested header text.
- [ ] No index column (`index=False`), no helper/debug columns, no extra sheets.
- [ ] Row count equals the number of inputs; rows sorted as specified (usually lexicographic by filename).
- [ ] Numeric-looking fields that must be strings (e.g., amounts formatted as `"47.70"`) are written as Python `str`, not `float`. Floats lose trailing zeros and change the cell type.
- [ ] Missing/unparseable values are written as real nulls (Python `None` / `pd.NA`), producing empty cells — never `""`, `"None"`, `"NaN"`, `"nan"`, `0`, or `0.00`.

### Null Handling (MANDATORY for every strict-schema output)

The single most common line-by-line grading failure is writing `""` (empty string) into a cell that the task spec says must be `null`. The empty string is a non-null value and mismatches an empty oracle cell. Apply BOTH steps on every strict-schema write:

1. **Pre-write sanitization.** Immediately before `to_excel`, coerce any falsy-string sentinel to real `None`:

   ```python
   SENTINEL_NULLS = {'', 'None', 'none', 'NONE', 'NaN', 'nan', 'NAN', 'null', 'NULL'}

   def sanitize_nulls(df, nullable_cols):
       for col in nullable_cols:
           df[col] = df[col].astype('object')
           df[col] = df[col].where(~df[col].isin(SENTINEL_NULLS), None)
           df[col] = df[col].where(df[col].notna(), None)
       return df
   ```

2. **Post-write verification.** Re-read the file and assert that cells intended to be null round-trip as real nulls, and that non-null formatted fields match the expected regex. If any assertion fails, fix and rewrite before claiming done.

### Canonical Pattern (extraction → strict Excel)

```python
import re
import pandas as pd

SENTINEL_NULLS = {'', 'None', 'none', 'NONE', 'NaN', 'nan', 'NAN', 'null', 'NULL'}

def sanitize_nulls(df, nullable_cols):
    for col in nullable_cols:
        df[col] = df[col].astype('object')
        df[col] = df[col].where(~df[col].isin(SENTINEL_NULLS), None)
        df[col] = df[col].where(df[col].notna(), None)
    return df

rows = []  # list of dicts in exact column order
for img_path in sorted_image_paths:
    fields = process_receipt(img_path)   # {'date': str|None, 'total_amount': str|None}
    # Guard at the row-construction boundary: never let '' / 'None' sneak in.
    d = fields.get('date')
    a = fields.get('total_amount')
    if isinstance(d, str) and d in SENTINEL_NULLS:
        d = None
    if isinstance(a, str) and a in SENTINEL_NULLS:
        a = None
    rows.append({
        'filename': img_path.name,
        'date': d,
        'total_amount': a,
    })

df = pd.DataFrame(rows, columns=['filename', 'date', 'total_amount'])
df = df.sort_values('filename', kind='stable').reset_index(drop=True)
df = sanitize_nulls(df, ['date', 'total_amount'])

out_path = '/app/workspace/stat_ocr.xlsx'
with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='results', index=False)

# --- Post-write verification (MANDATORY) ---
check = pd.read_excel(out_path, sheet_name=None, dtype=object)
assert list(check.keys()) == ['results'], check.keys()
r = check['results']
assert list(r.columns) == ['filename', 'date', 'total_amount'], r.columns.tolist()
assert list(r['filename']) == sorted(r['filename']), 'filenames not lexicographically sorted'

amount_re = re.compile(r'^\d+\.\d{2}$')
date_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
for idx, row in r.iterrows():
    a = row['total_amount']
    d = row['date']
    if pd.notna(a):
        assert isinstance(a, str) and amount_re.fullmatch(a), (idx, repr(a))
    if pd.notna(d):
        assert isinstance(d, str) and date_re.fullmatch(d), (idx, repr(d))
    # Explicitly reject falsy-string sentinels in nullable columns.
    for v in (a, d):
        if isinstance(v, str):
            assert v not in SENTINEL_NULLS, (idx, repr(v))
```

### Pitfalls That Break Line-by-Line Grading
- Writing `47.7` (float) instead of `"47.70"` (str) — Excel shows `47.7`, grader sees mismatch.
- Writing `""` for a failed extraction instead of a real null — the empty string is a distinct non-null value for cell-by-cell comparison. Always coerce failure sentinels to Python `None` before writing.
- Leaving `NaN` in cells (pandas default) instead of `None` — some readers surface it as the string `"nan"`.
- Letting pandas create a default `Sheet1` by not specifying `sheet_name`.
- Forgetting `index=False` — adds an unlabeled leading column.
- Sorting numerically or by OS listing order instead of lexicographic filename — row order mismatch.
- Keeping thousand separators or currency prefixes (`"RM 1,234.56"`) in the value — grader expects `"1234.56"`.
- Including a `success`/`confidence`/`raw_text` debug column — any extra column fails.
- Using `df.fillna('')` or `openpyxl` cell assignments of `''` for missing values — same as the first pitfall.
- Building `total_amount` via `str(x)` or f-string on a possibly-`None` value — yields the literal string `'None'`. Use a guarded conditional and keep `None` as `None`.

## Reading and Analyzing Data

```python
import pandas as pd

df = pd.read_excel('file.xlsx')                     # first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # dict
df.head(); df.info(); df.describe()
```

## Creating New Excel Files with openpyxl (formulas/formatting)

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active
sheet.title = 'results'
sheet.append(['filename', 'date', 'total_amount'])
sheet.append(['000.jpg', '2018-06-11', '47.70'])
wb.save('out.xlsx')
```

For strict-schema outputs prefer `pandas.to_excel` with an explicit `sheet_name` and `index=False` — it is less error-prone than hand-building rows, and it integrates cleanly with the `sanitize_nulls` step above.

## Use Formulas, Not Hardcoded Values (ANALYTICAL MODELS ONLY)

For analytical/financial models, keep calculations as Excel formulas so the workbook stays dynamic:

```python
sheet['B10'] = '=SUM(B2:B9)'
sheet['C5']  = '=(C4-C2)/C2'
sheet['D20'] = '=AVERAGE(D2:D19)'
```

**This guidance applies to analytical models and reports only.** For strict-schema extraction outputs every cell must be a literal value matching the oracle byte-for-byte — do NOT introduce formulas, totals, or helper columns, and do NOT trigger recalculation.

## Editing Existing Files (preserve formulas)

```python
from openpyxl import load_workbook
wb = load_workbook('existing.xlsx')      # keeps formulas
sheet = wb['SheetName']
sheet['A1'] = 'New Value'
wb.save('modified.xlsx')
```

Avoid `data_only=True` when you intend to re-save — it will replace formulas with their last cached values.

## Recalculating Formulas

openpyxl writes formulas as strings without cached results. Use the provided `recalc.py` script to recalculate via LibreOffice:

```bash
python recalc.py output.xlsx [timeout_seconds]
```

The script returns JSON; if `status` is `errors_found`, inspect `error_summary` and fix the offending formulas (#REF!, #DIV/0!, #VALUE!, #NAME?). Strict-schema extraction outputs contain no formulas, so recalculation is not required for them.

## Library Selection Guide
- **pandas**: strict-schema outputs, bulk data, analysis, simple exports.
- **openpyxl**: complex formatting, named styles, multi-sheet models with formulas.

## Code Style
- Write minimal, concise Python; avoid verbose prints.
- For Excel models, comment cells with complex formulas or hardcoded source citations.
- For strict-schema outputs, do the minimum needed to produce exactly the required bytes and verify by re-reading. Always run the post-write verification block — it is the single cheapest safeguard against silent format drift.
