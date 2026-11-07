# xlsx

## Purpose
Author, edit, and analyze spreadsheet files (.xlsx, .xlsm, .csv, .tsv) with correct semantics first and correct formatting second. The skill covers two tiers: (1) generic xlsx mechanics (openpyxl/pandas, formulas-not-hardcodes, recalc.py), and (2) analytical workflows where cells encode definitions (risk, exposure, "latest period", cross-sheet enumerations) that must be verified against task instructions before any formatting or error-cleanup step.

## When to Use
Use when the task requires producing or modifying a spreadsheet whose cells must carry specific semantic meaning (financial models, risk/exposure calculations, cross-sheet aggregations, time-series extractions). Do NOT fire this skill solely to apply formatting conventions on a workbook that already satisfies the task, and do NOT treat "zero formula errors" as sufficient success when the task defines semantic quantities. If the task is only "read a CSV and summarize", use pandas directly without this skill's authoring sections.

## Procedure
- Discover inputs and contract
- List available workbooks, sheet names, and column headers via `openpyxl.load_workbook(..., data_only=False)` and `wb.sheetnames`.
- Extract from the task instruction: required output path, required sheet/cell layout, named quantities (e.g., "exposure", "RaR", "latest"), and any explicit formulas. Record which quantities are DEFINED by the task and which are UNDEFINED.
- For every UNDEFINED quantity, either (a) ask the user for the definition, or (b) if asking is not possible, pick the most conservative, source-cited definition and record the citation and assumption in a cell comment. Never invent statistical constants (z-scores, horizon scalings) without an explicit source note.
- Enumerate data membership programmatically
- When the task references a set (e.g., "countries with 2025 data"), do not hand-pick. Scan every candidate sheet, filter rows where the relevant period column is populated and non-error, and build the set in code. Cross-check cardinality across all sheets that must agree (e.g., Value vs Volume) and report any asymmetry before writing outputs.
- Build dynamic references, not row literals
- For "latest period" or similar time-series lookups, construct formulas keyed on a date/period column using `INDEX`+`MATCH(MAX(...), ...)` or `XLOOKUP` with the max key. Row literals (e.g., `D430`) are forbidden for time-series cells; they are allowed only for header rows or layout anchors that are structurally fixed.
- Use Excel formulas for all computed values. Do not compute in Python and paste scalars.
- Prefer LibreOffice-compatible function names. If a function such as `NORM.S.INV` or `STDEV.S` is used, verify it survives recalc.py; if not, switch to the compatible variant (`NORMSINV`, `STDEV`).
- Semantic verification pass (BEFORE recalc.py)
- Emit a JSON log with: `assumed_definitions`, `enumerated_members`, `latest_period_key`, `cross_sheet_counts`, `source_cells_modified`. The `source_cells_modified` list MUST be empty for any sheet that is an input. If it is non-empty, revert the edits.
- Spot-check 2-3 output cells by hand against the source values.
- Recalculate and interpret errors non-destructively
- Run `python recalc.py <file>`. Read the JSON result.
- If errors exist: diagnose the ROOT CAUSE (missing source, wrong reference, incompatible function). Fix by correcting the formula or by surfacing the data gap in a clearly labeled note cell. Do NOT null, overwrite, or "clean" input source cells to make errors disappear.
- Bounded fallback: if a dynamic lookup cannot be constructed from available data, write a labeled placeholder formula that references an explicit assumption cell and document the gap; do not substitute a hardcoded row.
- Final checks
- Confirm: no row-literal references for time-series cells; no modifications to input sheets; every undefined quantity has a documented assumption; enumerations match across sheets; recalc.py reports success with semantics preserved.

## Constraints / Pitfalls
- Zero formula errors is a necessary but NOT sufficient condition. Semantic correctness (right definitions, right membership, right latest key) is the terminal success criterion.
- Never modify, blank, or overwrite cells in input/source sheets to suppress `#N/A`, `#DIV/0!`, or `#REF!`. Fix the referencing formula or document the data gap instead.
- Do not invent statistical definitions (confidence levels, horizon scaling, annualization factors). If the task does not state them, request them or record a cited assumption in a visible comment.
- Do not hand-pick set memberships. Enumerate programmatically from the sheets and cross-check cardinality.
- Do not hardcode row numbers for time-series "latest" lookups; use `MATCH(MAX(date_range), date_range, 0)` or `XLOOKUP` keyed on the max date.
- Use Excel formulas, not Python-computed scalars, for every derived value.
- Preserve existing template formatting; do not impose standardized styles on files with established conventions.
- Keep LibreOffice/recalc.py compatibility in mind when choosing function names; verify after writing.
- Output must be plain ASCII in any emitted logs or cell comments.