# xlsx-and-tabular-deliverable

## Purpose
Reusable workflow for producing tabular deliverables (`.xlsx`, `.xlsm`, `.csv`) when the task is one of: (A) plain data dump, (B) formula-bearing model, or (C) spreadsheet summarizing upstream extraction (OCR, scraping, parsing). Correctness is defined by both the structural contract and the row-value contract; the skill enforces both.

## When to Use
Use when the task deliverable is a spreadsheet or CSV file and the agent controls what rows and values go into it. Includes cases where the spreadsheet is the final container for upstream extraction results. Do not use for pure data-analysis tasks whose only output is a number or plot.

## Procedure
- Step 1 - Classify the branch and read the contract:
- Branch A (data dump): rows/columns already known; just write them.
- Branch B (model): formulas, cross-sheet links, or recalculated values required.
- Branch C (extraction summary): rows are derived from upstream parsing of source artifacts (images, PDFs, HTML, text).
- Read the exact output path, sheet name, column order, row semantics, and any field hints from the task text. Do not invent paths or schemas. Record expected row count if the task implies one (e.g., one row per input file).
- Step 2 - Extraction Contract (Branch C only; skip for A and B):
- Enumerate source items and the fields to extract per item.
- For each field, write down: inclusion keywords/anchors, exclusion keywords, expected format (regex), and the candidate-selection rule.
- Manually reconcile 2-3 sample source items end-to-end against the raw text before scaling up. If a sample fails, revise the rule, not the sample.
- Record a null policy: when extraction legitimately fails, write an empty cell rather than fabricating a value.
- Step 3 - Extraction Rules (Branch C):
- Candidate-selection ladder when multiple numeric or textual candidates match an inclusion keyword: try in order (1) first non-excluded match, (2) last non-excluded match, (3) match nearest to a stable anchor such as a cash/total/subtotal line, (4) max value. Choose the step whose result reconciles with the sample set; document the choice.
- Exclusion keywords should filter candidates only when they are the dominant signal on the line. If a line also matches the top-priority inclusion keyword, do not blanket-exclude it; downgrade its priority instead.
- OCR-noise repair: fix spaced decimals (e.g., `1 000 . 00`) only when surrounding digits confirm the pattern; disambiguate `,` vs `.` using regional format evidence in the same document; never silently insert a decimal point without a confirming anchor.
- Step 4 - Build the artifact:
- Branch A/C: use `openpyxl.Workbook()` or `pandas.DataFrame.to_excel(..., index=False)`. Preserve exact column order. Use empty cell for unknowns; never fabricate.
- Branch B: write formulas as `=`-prefixed strings; keep inputs separate from calculated cells; use cell references, not inline literals; match existing template formatting when editing.
- Step 5 - Recalculate (Branch B only): invoke the available recalc helper (discovered, not assumed); scan output for formula errors (`#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#N/A`); repeat until clean. Skip entirely for A and C.
- Step 6 - Two-tier Verification (all branches):
- Tier 1 structural: reload with `openpyxl.load_workbook(path)`; assert file exists at the exact task-specified path, target sheet present, headers match if required, row count equals the expected number of records.
- Tier 2 value-level: for each column, apply a format regex (dates, decimals, IDs) and compute non-null rate; spot-check at least 2 randomly sampled rows against the raw source. If a sample mismatches, return to Step 2/3 and revise the extraction rule rather than editing the output row directly.
- Fallback: if writing to the task-specified path fails, inspect mounts, permissions, and supported write routes; do not silently redirect to a different path.

## Constraints / Pitfalls
- Do not treat schema-only verification as sufficient when rows come from upstream extraction; passing shape with wrong values is a common silent failure.
- Do not commit to a single candidate-selection heuristic without reconciling against sample rows; use the ladder in Step 3.
- Do not let exclusion keywords override inclusion keywords on the same line; downgrade, do not delete.
- Do not fabricate values to fill nulls; empty cells are preferable to invented ones.
- Do not run the formula-recalculation branch when no formulas were authored.
- Do not hardcode paths, sheet names, keywords, or regexes beyond what the task text provides; discover from the task and the source documents.
- Keep code minimal; avoid speculative formatting or print noise outside the two-tier verification output.