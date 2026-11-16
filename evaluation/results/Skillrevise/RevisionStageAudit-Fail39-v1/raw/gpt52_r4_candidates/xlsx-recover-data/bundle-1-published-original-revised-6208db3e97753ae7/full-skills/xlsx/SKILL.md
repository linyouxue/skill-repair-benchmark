# Spreadsheet Edit and Verification (XLSX)

## Purpose
Safely create, edit, or repair Excel workbooks while preserving formulas and ensuring computed results are correct by using environment discovery, post-save recalculation, and verifier-aligned error checks.

## When to Use
Use when the task involves .xlsx/.xlsm workbooks where formulas, derived sheets, or template integrity matter (including "fill blanks", "recover a sheet", "update inputs", or "repair errors"). Do not use for simple CSV-only transformations, or when the user explicitly requires replacing formulas with fixed numbers.

## Procedure
- Step 1: Discover requirements and the workbook state (no edits yet).
- Identify the exact input workbook path(s) provided by the task and confirm they are readable.
- Open once with formulas visible (e.g., openpyxl with data_only=False) and determine:
- Whether target cells currently contain formulas, constants, or blanks.
- Whether edits will affect formula-dependent outputs (directly or indirectly).
- If requirements are ambiguous (e.g., whether to keep formulas vs fill static values), stop and resolve before writing.
- Step 2: Choose an edit strategy (decision point).
- If a value can be expressed as an Excel formula and the sheet is meant to stay dynamic, write a formula, not a Python-computed constant.
- Only write Python-computed constants when at least one is true:
- The task explicitly demands fixed numbers, or
- The workbook section is clearly a static data table (no downstream formulas), or
- The environment cannot recalculate and the task accepts static results (must be stated/confirmed).
- Step 3: Apply edits conservatively and preserve structure.
- Avoid operations that may destroy formulas/styles (e.g., do not load with data_only=True for any edit-save path).
- Make targeted cell edits; avoid broad reformatting unless the task requests it.
- Save to the required output path (or, if none is specified, save alongside the input with a clear derived name).
- Step 4: Recalculate and gate on formula errors (mandatory when formulas exist or are affected).
- Environment discovery:
- Check whether recalc tooling exists (e.g., recalc.py) and is runnable in the current environment.
- If formulas exist anywhere in the workbook OR your edits could affect derived cells:
- Run: python recalc.py <workbook_path> [timeout]
- Parse/inspect the JSON result and require an explicit no-error signal (e.g., status indicates success and total_errors equals 0).
- If errors are found: fix the referenced cells, save, and rerun recalc until clean (or stop and report an unresolvable environment/tooling issue).
- Step 5: Verify outputs using fresh values (post-recalc).
- Reload with data_only=False and confirm formulas are still present where they should be (no accidental formula-to-value loss).
- Reload with data_only=True after a successful recalc and run spot-checks that match the task contract (e.g., totals equal sum of components, percentages match numerators/denominators within stated rounding).
- Finalize only if: (a) recalc gate passed (when applicable), and (b) spot-checks pass or discrepancies are explained and corrected.

## Constraints / Pitfalls
- Never claim correctness based on openpyxl data_only=True unless you have just recalculated the same saved file; cached values can be stale and produce false confidence.
- Do not assume LibreOffice/recalc.py is available; discover tooling first. If recalculation is required by the task but the tool is missing or fails, stop and escalate with a concrete description of what was found (missing script, permission issue, headless office failure) instead of silently switching to a non-recalc workflow.