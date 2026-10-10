# xlsx

## Purpose
Author, edit, and verify spreadsheet files (.xlsx, .xlsm, .csv, .tsv) so that formulas, structure, and any required external inputs are present and recomputed without errors. Favor formulas over Python-computed constants so the artifact stays dynamic.

## When to Use
Use when the task requires producing or modifying a spreadsheet whose correctness depends on cell formulas, cross-sheet references, external data pulled into cells, or an in-workbook calculation (including optimization). Do not use for pure tabular data dumps where a CSV via pandas is sufficient, and do not apply the financial-modeling style appendix unless the task explicitly asks for a financial model or an existing template already uses those conventions.

## Procedure
- Scope the artifact. Identify: output path, required sheets, external datasets needed, and whether the model requires optimization (Solver, root-finding, iterative calc). Decide tool: pandas for bulk data, openpyxl for formulas/formatting.
- Acquire external inputs with a bounded discovery policy.
- First attempt a documented API or direct file endpoint for the publisher (e.g., statistical agency SDMX, dataverse file-id download, publisher-hosted file). Save raw inputs to disk.
- Cap blind URL probing at a small number of attempts (e.g., <= 5). If the endpoint is still unknown, switch to a browser-automation tool such as Playwright MCP to navigate the publisher page and capture the real download link; do not keep guessing with curl.
- Record the resolved source URL and retrieval timestamp in a cell note or a `sources` sheet.
- Populate the workbook.
- If editing an existing file, `load_workbook` and match its existing style, headers, and cell layout; do not re-impose a different convention.
- Write values as data, computations as formulas (`=SUM(...)`, `=AVERAGE(...)`, cross-sheet refs `Sheet!A1`). Place assumptions in dedicated input cells and reference them.
- Handle in-workbook optimization explicitly. `recalc.py` recomputes formulas but does not run Solver. Either (a) express the problem in closed-form formulas, or (b) drive Solver via a LibreOffice headless macro, or (c) implement the solver loop in Python and write both the parameter cells and the resulting values, with a note documenting the method.
- Recalculate and verify. Run `python recalc.py <file>`; parse the JSON. Required evidence: `status = success` and `total_errors = 0`. If `errors_found`, fix the listed cells (#REF!, #DIV/0!, #VALUE!, #NAME?, #N/A) and rerun until clean.
- Spot-check 2-3 computed cells against hand-calculated or source values before declaring done.

## Constraints / Pitfalls
- Do not hardcode calculated numbers that should be formulas; the workbook must recompute when inputs change.
- Do not save a workbook that was opened with `data_only=True` (formulas will be lost).
- Do not spend unbounded iterations on URL discovery; escalate to browser automation after the cap.
- Do not claim completion while `recalc.py` reports any formula errors.
- Apply the financial-model color and number-format conventions (blue inputs, black formulas, green cross-sheet, red external; parentheses negatives; `-` zeros; `0.0x` multiples) only when the task is a financial model or an existing template already uses them; otherwise skip to avoid context pollution.
- Avoid hardcoding specific publisher URLs or dataset file IDs in this skill; resolve them per task via discovery.
- Prefer `read_only=True` / `write_only=True` for very large files; otherwise standard `load_workbook` / `Workbook`.