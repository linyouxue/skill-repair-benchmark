# xlsx-and-tabular-qa

## Purpose
Reusable procedure for two related task families: (A) authoring or editing spreadsheets (.xlsx, .xlsm, .csv, .tsv) with correct formulas and formatting, and (B) read-only analysis or question answering over tabular data, often governed by a separate rules or specification document. The skill branches on task type so authoring rules do not pollute QA tasks and vice versa.

## When to Use
Use when the task involves spreadsheets or tabular data. Decide mode first: Authoring Mode: the deliverable is a spreadsheet file to be created or modified. QA / Analysis Mode: the deliverable is an answer (number, string, short text, or report) derived from tabular data, possibly combined with a rules/specification document. No spreadsheet output is required. If both apply, run QA Mode first to establish the contract, then Authoring Mode for any file deliverable.

## Procedure
- ### Step 0: Mode selection and contract capture
- Read the task statement and any referenced files. Classify as Authoring Mode or QA Mode.
- Record a Verifier Contract: exact output path(s) (as given by the task; do not invent), expected format (plain number, JSON, xlsx, etc.), and any explicit success criteria. If a path or format is not stated, note "unknown" rather than guessing.
- Discover the environment before fixed commands: list the working directory, locate referenced inputs, and check which tools are available (python, pandas, openpyxl, libreoffice, pdf text extractor). Do not assume any specific script name or absolute path exists. ### QA / Analysis Mode
- Input inventory. List every input file and its role (data vs. rules/spec vs. examples). For PDFs or docs that define scoring, matching, or interpretation rules, treat them as the contract source.
- Rules Ledger (mandatory execution anchor). Before any computation, extract each rule you intend to apply. For every rule record:
- A short name.
- A verbatim quote from the source document plus page/section locator.
- The restated assumption in your own words.
- Any parameters (thresholds, point values, tie-breakers, ordering). If a required rule cannot be grounded in a quote, stop and either ask for clarification or explicitly mark it as an assumption and flag the risk; do not silently invent rules or point values.
- Data integrity probe (mandatory execution anchor). Load data with pandas or equivalent and assert expected structure before computing:
- Row/record counts match any stated expectation (e.g., N games x M turns).
- No missing or duplicate keys on identifying columns.
- Value ranges and types are plausible (e.g., dice in 1..6, non-negative counts). Print a short integrity report. If anomalies exist (missing turn, duplicate row, out-of-range value), halt and resolve explicitly: consult the rules document for the correct handling or report the ambiguity. Do not impute zeros or defaults silently.
- Computation. Implement the logic strictly from the Rules Ledger. Keep intermediate results inspectable (per-row scores, per-group aggregates). Prefer small, testable functions over one-shot expressions.
- Independent verification (mandatory execution anchor). Recompute the final answer by a second method or sanity bound:
- Alternative implementation (e.g., vectorized vs. loop, or brute-force vs. closed-form).
- Bounds check (min/max feasible values given the rules).
- Spot-check 2-3 individual records by hand against the Rules Ledger. If the two methods disagree, do not finalize; reconcile first.
- Deliver. Write the answer to the exact task-specified output path and format. Read the file back and confirm its contents and encoding (plain ASCII unless the task says otherwise). If no path was specified, present the answer in the response and note the absence of a path. ### Authoring Mode
- Choose library: pandas for bulk data IO and analysis; openpyxl for formulas, styles, and structural edits. For existing templates, load with openpyxl and match existing conventions exactly; template conventions override generic guidelines below.
- Build the workbook using formulas rather than Python-computed constants for any value that should remain dynamic (totals, ratios, growth rates, averages). Place assumptions in dedicated cells and reference them from formulas.
- Prevent formula errors: verify ranges, avoid off-by-one, guard denominators, keep cross-sheet references in `Sheet!Cell` form, and avoid unintended circular references.
- If the deliverable requires computed values to be present (not just formulas), recalculate using the available tool chain. Discover it rather than hard-coding: check for a project-provided recalc script, otherwise invoke LibreOffice headless if installed, otherwise report that recalculation is unavailable. Do not assume any specific script path.
- Post-write validation (execution anchor for Authoring Mode): reopen the saved file and scan all cells for Excel error sentinels (`#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, `#NAME?`). Zero errors is required before declaring completion. Fix and re-run until clean.
- Optional financial-model conventions (apply only when the task is a financial model and no template dictates otherwise): blue for hardcoded inputs, black for formulas, green for intra-workbook links, red for external links, yellow fill for key assumptions; years as text, currency as `$#,##0`, zeros as `-`, percentages one decimal, multiples `0.0x`, negatives in parentheses. Skip entirely in QA Mode.

## Constraints / Pitfalls
- Mode discipline: never apply Authoring Mode formatting, recalc, or color rules to a QA task. QA Mode never produces a spreadsheet unless explicitly requested.
- No invented contracts: scoring rules, matching rules, tie-breakers, and point values must be grounded in quoted source text. If missing, treat as an open question, not a default.
- No silent imputation: missing or anomalous rows halt computation until explicitly resolved with cited justification.
- No hard-coded paths, script names, or tool versions: discover them. Treat examples like answer file paths or recalc scripts as placeholders unless the current task supplies them verbatim.
- Independent verification is required before finalizing a QA answer; a single-method result is not acceptable.
- Plain ASCII only in written outputs unless the task explicitly requires other characters.
- Keep intermediate reasoning (Rules Ledger, integrity report, verification result) available for inspection; do not discard them before writing the final answer.