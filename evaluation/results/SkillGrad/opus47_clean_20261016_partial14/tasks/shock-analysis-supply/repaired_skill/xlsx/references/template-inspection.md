# Template inspection before writing

Trigger: the task supplies a workbook template with multiple sheets, a
metadata/notes/README sheet, or a column whose intended source variable is
ambiguous from the header alone.

The inspection pass answers four questions before any write happens:

1. **What sheets exist, and does any sheet carry metadata/notes/definitions?**
2. **For each column I plan to fill: what is the exact header text, what units does it imply, what year/row range does it span?**
3. **If my raw source ships its own metadata/variable-definitions sheet, which of its variables matches each template column?**
4. **Does the required horizon (last filled column) extend past the end year of the mandated source?** (If yes, see `live-data-acquisition.md`'s extension-gap branch — do not plan a CAGR.)

## Runnable inspection pass

```python
from openpyxl import load_workbook

wb = load_workbook(template_path)
report = {}
for name in wb.sheetnames:
    ws = wb[name]
    # Capture top-left block to find header rows and any notes text
    preview = []
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 10),
                            values_only=True):
        preview.append(row)
    report[name] = {
        "dims": (ws.max_row, ws.max_column),
        "preview": preview,
    }

# Identify metadata-like sheets by name OR by low row count + prose content
META_HINTS = ("notes", "readme", "metadata", "definitions", "variables",
              "dictionary", "legend", "about")
meta_sheets = [n for n in wb.sheetnames if any(h in n.lower() for h in META_HINTS)]
```

### Branch A — a metadata/notes sheet exists

Open and READ it in full. Record every variable definition and every unit
note. Only then decide which source variable fills each template column.

```python
if meta_sheets:
    for name in meta_sheets:
        ws = wb[name]
        for row in ws.iter_rows(values_only=True):
            # print or log every row; do not skip
            print(name, row)
```

### Branch B — no metadata sheet, headers alone must disambiguate

For each column to fill, record the exact header string and look for unit
hints embedded in it (`$mm`, `(ratio)`, `%`, `index`, `GEL millions`). Match
these to the source's own variable list. If the match is still ambiguous
after reading the source's variable catalog, treat it as a blocker to
surface — do NOT guess.

```python
headers = {col: ws.cell(row=header_row, column=col).value
           for col in range(1, ws.max_column + 1)}
ambiguous = [col for col, h in headers.items()
             if h and not any(hint in str(h).lower()
                              for hint in ("ratio", "index", "$", "%", "mm",
                                           "millions", "billions", "gel",
                                           "usd", "eur"))]
```

## Unit-scale handling

When the template header implies units different from the raw source,
convert in Python, write the converted number, and add a cell comment on
the first data cell of that column that shows the explicit conversion
factor (e.g. `"GEL / 1_000_000 — header reads 'GEL millions'"`). Never
scale on judgment alone.

```python
from openpyxl.comments import Comment

sheet.cell(row=first_data_row, column=col).value = raw_value / 1_000_000
sheet.cell(row=first_data_row, column=col).comment = Comment(
    "Scaled: raw GEL / 1_000_000 — header reads 'GEL millions'",
    "inspector"
)
```

## Verification step

After writing, re-open the saved workbook with `data_only=False` and
confirm, for every column you filled:

- The header you read at inspection time still matches what is in the file
  (you did not accidentally overwrite the header row).
- The first data cell for each column carries a provenance comment naming
  the source and, where applicable, the unit conversion.

```python
wb2 = load_workbook(output_path)
ws2 = wb2[target_sheet]
for col in filled_columns:
    header_now = ws2.cell(row=header_row, column=col).value
    assert header_now == recorded_headers[col], (
        f"header for col {col} changed: {recorded_headers[col]!r} -> {header_now!r}"
    )
    first = ws2.cell(row=first_data_row, column=col)
    assert first.comment is not None, (
        f"col {col} missing provenance comment at {first.coordinate}"
    )
```

**On failure:** if the header-match assertion fires, re-open the original
template, re-record the header text, and rewrite the data cells WITHOUT
touching the header row. If the comment assertion fires, iterate the
filled cells and attach the missing provenance comment before saving
again — do not ship the workbook with un-sourced raw-data cells.
