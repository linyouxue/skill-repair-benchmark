# Excel-only execution guardrail

Use this when the task/evaluator requires working strictly inside Excel (interactive editing) and disallows programmatic workbook modifications.

## Trigger

You should activate this guardrail when you see any of:
- Instructions like “ONLY use Excel”, “no Python”, “no scripts”, “don’t use openpyxl”.
- An evaluation setup where only the final `.xlsx` contents matter and programmatic writes are likely to produce an unchanged template.

## Procedure (with branch)

```python
# This is a planning gate (not a workbook-editing implementation).
# Branch A: Excel-only required
excel_only_required = True  # set based on task instructions

if excel_only_required:
    plan = [
        "Open workbook in Excel UI",
        "Locate target sheets + ranges",
        "Ingest external data via browser/download, then paste into landing ranges",
        "Enter formulas in template cells (as Excel formulas)",
        "Run Solver/what-if tools if required by the model",
        "Save workbook and re-open to verify ranges are filled",
    ]
else:
    plan = [
        "Programmatic edits allowed; use an xlsx library to write values/formulas",
        "Still run a completion gate before saving",
    ]

assert len(plan) > 0
```

- **Branch A (Excel-only required):** do not attempt openpyxl edits; treat Python as inspection/planning only if permitted.
- **Branch B (programmatic edits allowed):** proceed with library-based writes, but keep the same dependency-order build and completion gate.

## Verification (what to do on failure)

After your first pass, verify the deliverable is not an unchanged template:
1. Re-open the saved workbook.
2. Check at least one required landing range contains non-empty values.
3. Confirm at least one expected formula region contains formulas.

If any check fails: stop and return to the mapping table (`required_output → landing range`) and re-execute the ingest→paste and formula-entry steps inside Excel before doing any further external searching.
