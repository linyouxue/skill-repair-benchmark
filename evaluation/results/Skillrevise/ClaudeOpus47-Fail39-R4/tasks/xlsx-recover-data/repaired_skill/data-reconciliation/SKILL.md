# Spreadsheet Value Reconciliation

## Purpose
Recover missing cell values in multi-sheet workbooks using row/column sums, percentage shares, YoY changes, CAGR, and cross-sheet identities, while preserving each cell's native precision and number format so that filled values match an external verifier exactly.

## When to Use
Apply when a workbook contains placeholder cells (e.g., `???`, blanks in labeled grids, or sentinel markers) whose values are determined by arithmetic relationships to other cells in the same or other sheets, and the task will be graded against hidden ground-truth numeric values.

## Procedure
- Discover: Load the workbook read-only first. Enumerate every placeholder cell across all sheets. For each placeholder record: sheet name, coordinate, row label, column label, and the `number_format` of the nearest non-empty cell in the same column (fallback: same row). Print this inventory before any writes.
- Model constraints: For each placeholder, list every independent constraint that determines it (row total, column total, share-of-total, YoY %, CAGR, average, cross-sheet equality). Prefer a direct identity (exact sum or stated equality) over a back-solve through a rounded percentage or mean. Mark each placeholder with its chosen primary constraint and at least one independent secondary constraint for cross-check.
- Build dependency DAG: Order placeholders so that any cell used as an input to another placeholder's formula is solved first. Place exact-integer / exact-sum cells before cells derived from percentages or means. If a cycle exists, solve it as a simultaneous system rather than by guessing an order.
- Solve without rounding intermediates: Compute each placeholder using full floating precision from original source cells only. Never feed a just-computed, rounded value into another placeholder's formula; always re-read the unrounded computed value or recompute from originals. Apply rounding only at the moment of writing, using the recorded `number_format` of that cell's column/row neighbor; do not invent a precision by eyeballing.
- Write and preserve format: Write each value and explicitly set the destination cell's `number_format` to the sampled neighbor's format. Save the workbook.
- Verify by reload: Reopen the saved workbook. For every placeholder coord, recompute its value from the most direct constraint using only cells that were non-placeholder in the original workbook (not from other filled cells). Assert recomputed equals stored (within display precision) and `number_format` matches the sampled neighbor. If any check fails, revisit the DAG and constraint choice; do not finalize until all pass.

## Constraints / Pitfalls
- Do not round intermediates. Rounding is a write-time operation only; computations and chained derivations must use unrounded values.
- Never use a just-filled cell as input to compute another placeholder; always derive from original source cells, especially for exact-integer totals.
- Prefer direct constraints (row sum, stated equality) over back-solving through percentages, means, or CAGR when both are available; percentages shown in the sheet are typically already rounded.
- Infer precision from the sheet, not from assumptions: sample `number_format` from a neighboring data cell in the same column; do not pick 1 vs 2 decimals by inspection of printed values.
- Self-consistency is not sufficient. Final verification must recompute each filled cell from original source cells after reloading the saved file.
- Keep rules general: refer to cells by role (same-column neighbor, row total cell, prior-year cell), not by hard-coded coordinates or sheet names from any single task.