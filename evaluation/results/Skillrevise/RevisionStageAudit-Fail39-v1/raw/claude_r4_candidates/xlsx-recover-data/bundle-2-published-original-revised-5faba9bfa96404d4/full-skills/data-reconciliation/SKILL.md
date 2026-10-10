# Spreadsheet Data Reconciliation

## Purpose
Recover missing cells in multi-sheet xlsx workbooks by combining row/column totals, percentage shares, year-over-year changes, and CAGR relationships as a joint constraint system, writing results as numeric values at the precision each cell's existing number_format implies, and validating by reloading the file.

## When to Use
Apply when a workbook contains sentinel-missing cells (blank, "???", NaN, or similar) and the surrounding sheets expose enough totals, shares, YoY percentages, or growth rates to determine those cells mathematically. Suitable whenever recovery must satisfy an external verifier rather than only internal self-consistency.

## Procedure
- Discover: list sheet names, dimensions, headers, and the exact set of missing cells (addresses, sheet, row/column labels). Record each missing cell's existing number_format and that of its column/row siblings to derive expected decimal precision.
- Enumerate constraints: for each sheet, extract every stated total, subtotal, share%, YoY%, and CAGR, noting which cells participate. Cross-reference labels across sheets to link the same entity (e.g., same program, same year).
- Build constraint graph: nodes = unknown cells, edges = equations relating them. Mark rows/columns with exactly one unknown as directly solvable; mark the rest as requiring joint solving.
- Solve in dependency order: resolve single-unknown constraints first; for any row or column with multiple unknowns, combine it with the matching share%, YoY%, or CAGR constraint from another sheet to form a solvable linear/nonlinear system. Never fill a multi-unknown row by assuming an average or any value not explicitly given as a constraint.
- Write: assign numeric (not string) values to each target cell. Round using the precision derived from that cell's number_format (or its column siblings if the target cell itself has none). Preserve existing cell styles and number_format strings.
- Validate (execution anchor): save, then reopen the workbook from disk. For every filled cell, recompute each constraint it participates in (row sum, column sum, share%, YoY%, CAGR) and assert |computed - stated| <= 10^(-decimals_implied_by_number_format). Also recompute at least one constraint that was not used to derive the value, as an independent cross-check. Any FAIL blocks finalization; return to the solve step.

## Constraints / Pitfalls
- Do not pick rounding precision arbitrarily; always derive it from the target cell's or sibling cells' number_format. If no format is present, match the precision of adjacent known values in the same column.
- Do not infer an unknown from an assumed average, assumed equal-split, or any value not stated as a constraint in the workbook. If a row has multiple unknowns, you must find an additional cross-sheet constraint (share%, YoY%, CAGR) before solving.
- Do not declare success on internal self-consistency alone; always perform the reload-and-recompute validation step on the saved file.
- Write numeric types (int or float), never strings or formatted text. Preserve sheet structure, column widths, and formats; modify only the target cells.
- Do not hardcode output paths, sheet names, or cell addresses; discover them from the input workbook each run.
- If constraints are inconsistent or underdetermined after graph construction, stop and report the ambiguity rather than guessing.