# xlsx

## Purpose
Create, edit, and analyze spreadsheet files (.xlsx, .xlsm, .csv, .tsv) with correct formulas, cross-sheet links, and scenario structures. Keep workbooks dynamic: every computed cell is a formula referencing assumption cells, never a Python-computed literal.

## When to Use
Trigger when the task requires producing or modifying a spreadsheet deliverable, especially models that (a) combine external data with internal calculations, (b) replicate scenario or shock blocks, or (c) must preserve an existing template. Do not trigger for pure text extraction or when a non-spreadsheet format is explicitly requested.

## Procedure
- Discover environment and contract.
- List target output path(s), required sheet/table names, and any template to preserve.
- Probe the environment for a formula-recalculation tool (e.g., `which libreoffice`, look for a provided `recalc.py` or equivalent). Record the exact command found; do not assume a fixed path.
- Choose library per subtask: pandas for bulk data I/O and analysis; openpyxl for formulas, cross-sheet links, and formatting. Load existing files with openpyxl (not `data_only=True`) to preserve formulas.
- Plan inputs (input ledger checkpoint).
- Before any download or heavy computation, write a short input ledger: for each input variable list {name, source, target sheet!cell or range, fallback assumption if source unreachable}.
- Identify which cells are assumptions (user-editable) vs. derived (formula). Assumptions get their own named block or sheet.
- Acquire external data with a bounded fallback.
- Prefer direct file URLs (xlsx, csv) over scraping APIs or JS bundles.
- Set a hard attempt budget for data acquisition (e.g., N tool calls per source). If the budget is exhausted or the endpoint is gated, do not keep probing: fall back to the ledger's documented assumption, record `Source: assumption, [reason]` next to the cell, and proceed to step 4.
- Validate acquired data shape (rows, columns, units, year coverage) before writing to the workbook.
- Build source sheets, then link.
- Write raw inputs to dedicated source sheets with headers and units.
- In calc sheets, reference source cells by formula (e.g., `=Source!B5`), never paste values. Place assumptions in a clearly labeled block and reference them with absolute addressing (`$B$6`) in formulas.
- Replicate scenario blocks by structural copy.
- For each scenario, duplicate the base table's structure with a fixed row/column offset. Override only the assumption cell(s) that define the scenario (e.g., shock multiplier, share parameter). All derived formulas must remain identical in form so results differ only through the overridden assumption.
- Verify by spot-check: changing a base assumption should propagate to the base block only; changing a scenario assumption should affect only that scenario.
- Recalc and verify.
- Save the workbook, then run the recalculation command discovered in step 1 against the output file.
- Inspect the recalc report (or re-open with `data_only=True` in a separate read) for `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#N/A`. If any appear, fix the referenced cell and recalc again. Do not deliver with unresolved error tokens.
- Spot-check 2-3 key output cells against hand calculations or source values.
- Recover.
- If recalc tool is unavailable: document that formulas are present but uncalculated, and ensure formula correctness by structural review and a minimal Python re-evaluation of 2-3 cells.
- If a required input remains missing after the acquisition budget, deliver the model with the assumption cell flagged (e.g., yellow fill or inline note) and a one-line source note.

## Constraints / Pitfalls
- No hardcoded computed values. Every total, ratio, growth rate, or scenario output must be an Excel formula referencing assumption or source cells. Python computes inputs, Excel computes results.
- Time-box external data acquisition. Do not iterate indefinitely on JS/API endpoints; fall back to a documented assumption once the budget is spent.
- Preserve existing templates exactly: match sheet names, header rows, column order, and number formats when editing a provided file. Template conventions override generic style guidance below.
- Generic formatting defaults (apply only when no template exists): blue for hardcoded inputs, black for formulas, green for intra-workbook links, red for external links, yellow fill for assumptions needing review; currency as `$#,##0;($#,##0);-`; percentages one decimal; years as plain integers without thousands separators.
- Document source for every hardcoded input in an adjacent cell or comment: `Source: [system/document], [date], [reference]`. For fallback assumptions: `Source: assumption, [brief rationale]`.
- Do not open-and-save with `data_only=True`; it strips formulas permanently.
- Keep the skill's influence proportional: if the task is pure data analysis with no spreadsheet deliverable, skip steps 4-6.