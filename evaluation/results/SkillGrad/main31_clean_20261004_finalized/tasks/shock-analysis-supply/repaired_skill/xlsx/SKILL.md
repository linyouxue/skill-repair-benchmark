---
name: xlsx
description: Populate and verify Excel workbooks by mapping requirements to exact sheet ranges, choosing Excel-only vs programmatic execution up front, writing formulas in dependency order with early ingest checks, timeboxing external data with modality pivots, and running completion gates on the deliverable before saving.
---

## Plan the build (template-first)

1. Open the workbook and locate every required output table by **sheet name + exact cell range**.
2. Make a mapping table: `required_output → source_series → transform → landing sheet+range`.
3. Decide execution mode from constraints: **Excel-only UI** vs programmatic writes; once chosen, treat later prompt wording as metadata, not a directive to switch modes mid-run.
4. Write a cell-level plan: for each landing range, record (a) source data, (b) required formulas/links, (c) dependencies.
5. Implement in dependency order: **raw data → links → derived calculations → summaries/outputs**.
6. Prefer Excel formulas over computed constants for anything derived from workbook inputs.
7. After each external-source attempt (success or failure), do an **ingest check** on the deliverable workbook: if any required landing range is still empty, stop external work and complete extract→paste/formulas for that range before moving on.
8. Require an early milestone: populate **one full upstream chain** (one source → landing range → at least one downstream linked/derived region) before attempting additional external retrieval.
9. Timebox external data acquisition attempts; pivot quickly to alternate sources or smaller extracts.
10. Save only after passing a completion gate (non-empty required ranges, formulas present, key-cell spot checks).

Decision rule: if initial inspection shows any required landing range is blank, enter an **Excel build loop**: fill one complete source→landing range→downstream formula chain, then re-check required ranges before further retrieval.

Read references/excel_only_execution.md when the task/evaluator requires “Excel-only” editing (no Python/openpyxl) or when you see explicit constraints like “ONLY use excel”. Skip when programmatic workbook edits are explicitly allowed.

## Acquire external data without stalling

Use a fallback-first approach when a task requires external macro/market datasets.

```python
import pandas as pd

def fetch_table(spec, read_fn):
    try:
        return read_fn(spec)
    except Exception:
        return None

primary = "https://example.com/data.xlsx"
fallback = "local_copy.xlsx"

df = fetch_table(primary, pd.read_excel) or fetch_table(fallback, pd.read_excel)
```

Decision rule: if you hit 403/429/anti-bot pages, SSL/API errors, or slow parsing, **switch modality** (browser/Playwright download/export) or use a bulk downloadable artifact, then immediately ingest into the workbook and re-run the ingest check.

Read references/external_data_timeboxing.md when the task needs multiple external sources and you hit access blocks, slow parsing, or uncertainty about extract→paste completion. Skip when all data is already inside the provided workbook.

## Populate required ranges with formulas (not hardcodes)

When a template expects computed values, write formulas into the specified cells and keep assumptions in separate input cells.

```python
from openpyxl import load_workbook

wb = load_workbook("input.xlsx")
ws = wb["Sheet1"]

ws["B2"] = "=A2*($D$1)"   # derived value via assumption cell
ws["D1"] = 0.1            # assumption/input

wb.save("output.xlsx")
```

Decision rule: if a number should change when upstream data changes, it should be a formula (or a link), not a Python-calculated constant.

## Completion gate before saving

Run a completion gate on the **deliverable workbook** repeatedly (not just at the end): after any large paste/import, after building a formula region, and before final save.

```python
from openpyxl import load_workbook

wb = load_workbook("output.xlsx")
ws = wb.active

# spot-check: some formulas exist
formula_cells = [c for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
assert len(formula_cells) > 0, "no formulas written"
```

Decision rule: if the gate fails, stop—return to the workbook and fill the missing landing ranges and formula regions in dependency order; do not continue external browsing.

Read references/completion_gate.md when you must guarantee specific sheet ranges are filled and formulas exist (e.g., templates with many dependent tabs) or when the output might be an unchanged template. Skip when the deliverable is a one-off, value-only paste with no downstream calculations.

## Common Pitfalls

- Choosing tools from habit: missing an explicit Excel-only/no-script constraint causes “edits” that never happen in the workbook UI.
- Starting external browsing before mapping each required output to an exact landing sheet+range; this often leads to “found data” but no ingest.
- Treating retrieval as progress: a download/terminal dataframe is not done until the landing cells in the workbook are non-empty and the model recalculates.
- Stalling on a blocked/slow data source; timebox attempts and pivot to a known downloadable artifact or a browser/Playwright export.
- Hardcoding derived values that should be formulas, breaking recalculation and downstream tabs.
- Saving without running the completion gate on the actual deliverable workbook (not the template or an intermediate file).
