# xlsx

## Purpose
Create, edit, analyze, and recover values in spreadsheet files (.xlsx, .xlsm, .csv, .tsv). Supports two distinct workflows: (A) authoring workbooks with formulas and formatting, and (B) recovering or imputing missing numeric values in a pre-formatted analytical workbook under strict representation constraints.

## When to Use
Use this skill when the task requires reading, writing, modifying, or completing a spreadsheet. Choose the Authoring workflow when creating or extending a model with formulas and formatting. Choose the Data Recovery workflow when the task gives a workbook with missing or placeholder cells (e.g., `???`, blanks in otherwise filled tables) that must be filled with specific numeric values matching the existing representation.

## Procedure
- ### Step 0 - Classify the task
- Inspect the input file(s). If the task is "fill missing cells / recover values / impute", go to Data Recovery. Otherwise use Authoring.
- Record which sheets, cells, or ranges are the targets. Do not proceed until the target set is explicit. ### Authoring workflow (new or extended models)
- Load or create with openpyxl (preserves formulas/formatting). Use pandas only for bulk data reads.
- Write formulas, not Python-computed constants, for any derived quantity (totals, ratios, growth, averages).
- Match existing template conventions exactly when editing an existing file (number formats, fonts, column widths, header style). Existing conventions override any default style guidance.
- Save, then run `python recalc.py <file> [timeout_seconds]`. Parse the returned JSON. If `status` is `errors_found`, fix each listed `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#N/A` and recalc again until `total_errors == 0`.
- Reload with `load_workbook(path, data_only=True)` and spot-check at least 3 computed cells against hand calculations. ### Data Recovery workflow (value imputation)
- Discover targets: enumerate every cell to fill. For each, identify its "peer group" (same row metric, same column series, same cross-sheet mirror if any). Record coordinates.
- For each target cell, read at least 3 non-missing peer cells and build a peer profile:
- raw stored value (`cell.value`, not displayed string)
- python type (int vs float)
- decimal digits in the raw value
- `cell.number_format` string (e.g., `0.00%`, `#,##0.00`, `0.0`, `General`)
- percent class: `is_percent_format = '%' in number_format`; `is_fraction_scale = is_percent_format and all(abs(v) <= 1 for v in peer_values)` Log this profile before writing anything. This is an execution anchor; the log must exist.
- Compute the imputed value using the task's stated identity (sum, average, ratio, difference, cross-sheet link). Preserve full precision during computation; do not pre-round.
- Normalize the value to peer representation:
- If `is_fraction_scale`, store as fraction (e.g., 0.2197), not as 21.97.
- If `is_percent_format` and peers are stored as numbers > 1 (e.g., 26.91), store as number with the same decimal count.
- Match the maximum decimal digit count observed among non-missing peers; never truncate below peer precision.
- Match python type: if all peers are int, cast to int only when the computed value is exactly integral; otherwise keep float and flag the mismatch.
- Write values with openpyxl. Do not overwrite `number_format` of target cells unless peers prove a different format is required.
- Save, then unconditionally run the post-write verification (below). Do not declare completion before it passes. ### Post-write verification (unconditional, runs for both workflows)
- Reload the saved file twice: once with `data_only=False` (to inspect formulas and `number_format`) and once with `data_only=True` (to inspect computed values). If any formulas were written, first run `python recalc.py <file>` and require `total_errors == 0`.
- For every imputed or written cell, assert:
- cell is not empty and not a placeholder string (`???`, `NaN`, `#N/A` as text).
- python type matches peer-profile type class (int vs float), or is a reconciled float when peers were mixed.
- decimal precision >= max peer decimals.
- percent scaling matches peers (fraction vs number).
- at least one independent identity holds on reload (e.g., row total equals sum of row components; cross-sheet mirror equals source).
- Print a per-cell PASS/FAIL table. If any FAIL, fix and re-verify. Only finalize when all assertions pass.

## Constraints / Pitfalls
- Do not self-author an ad-hoc internal validator and treat its success as task completion. The reload-and-assert step above is the only acceptable completion gate.
- Never guess precision or percent scaling; derive both from peer cells in the same workbook. If peers are missing, state the ambiguity rather than inventing a convention.
- Do not calculate values in Python and hardcode them when a formula is appropriate for the Authoring workflow. In the Data Recovery workflow, hardcoded values are expected, but they must still obey peer representation.
- Do not strip or standardize existing formatting on files that have established conventions. Existing template conventions override defaults.
- Avoid `data_only=True` followed by save; it destroys formulas. Use it only for read-side verification.
- Financial-model color coding, number-format defaults, and source-citation rules apply only when the user explicitly requests a financial model or when the existing template already uses them. Do not impose them on recovery tasks.
- Use plain ASCII in any string written as a cell comment or source note.
- If a required tool (e.g., LibreOffice for `recalc.py`) is unavailable, fall back to writing values without formulas for recovery tasks, document the fallback, and still run the reload-and-assert verification.