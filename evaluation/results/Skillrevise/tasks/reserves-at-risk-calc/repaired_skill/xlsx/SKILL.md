# XLSX Workbook Authoring and Repair (Verifier-Aligned)

## Purpose
Create, edit, and validate spreadsheet workbooks while preserving existing templates, keeping computations inside the workbook (when required), and producing verifier-aligned artifacts that recalculate with zero Excel error values.

## When to Use
Use this procedure whenever you must generate or modify .xlsx/.xlsm/.csv-derived workbooks that contain formulas, formatting, and model logic, especially when the environment uses a headless recalculation engine (for example LibreOffice) and the acceptance condition includes "zero formula errors" or "latest value" logic.

## Procedure
- 1) Intake and constraints gate (before touching files)
- Identify: input workbook(s), required output path(s), and any explicit restrictions (for example "only Excel for computation" or "preserve template exactly").
- If required output path is not specified, discover the verifier-visible output mount/location from the environment/task runner before proceeding.
- Decision: If the user requirement is ambiguous (for example what "latest" means: last nonblank row vs latest date), ask a single targeted clarification; otherwise assume "latest = last nonblank by date/key in the data column" and implement dynamically (no fixed indices).
- 2) Environment discovery (tools and invariants)
- Discover a formula recalculation/error-scan method available in the environment:
- Prefer a provided recalc script if present; locate it by searching known workspace roots and the current working directory (do not assume a fixed path).
- If a recalc script is not found, discover whether LibreOffice CLI is available for headless recalculation.
- Record the resolved tool and how to invoke it (exact command that works).
- Checkpoint: If neither recalc script nor LibreOffice is available, proceed with edits but you must add a bounded fallback verification step using a secondary scan (see step 6).
- 3) Load and inspect workbook (template-preserving)
- Load the workbook with a library that preserves formulas and formatting (for example an xlsx editor that keeps formula strings intact).
- Inventory: sheet names, named ranges (if any), and the areas you are allowed to change.
- If updating a template, copy its existing style and conventions; do not normalize formatting.
- 4) Make edits with workbook-native formulas (no Python-side computation of derived values)
- If the task says "only Excel for computation":
- Write derived values as spreadsheet formulas, not numeric constants produced by external computation.
- Use workbook functions or equivalent formula rewrites compatible with the recalculation engine you discovered.
- For "latest" / trailing-row references:
- Do not hardcode row numbers or fixed offsets for "latest".
- Use a dynamic pattern: last-nonblank lookup or date-keyed lookup (MATCH/XLOOKUP/LOOKUP-like) that resolves to the last populated record in the relevant series.
- Keep changes scoped: do not alter unrelated cells to silence errors unless the error is directly introduced by your changes or is required by acceptance criteria.
- 5) Pre-save validation checkpoint (prevent brittle or unsafe changes)
- Verify assumptions before saving:
- Any cells that must remain formulas are still formulas (not constants).
- No new external links were introduced unless explicitly requested.
- Any "latest" logic uses dynamic lookup, not fixed row/column indices.
- If you cannot implement a required formula due to function incompatibility, rewrite using a more compatible equivalent; if no equivalent exists, stop and request guidance rather than hardcoding.
- 6) Save, recalculate, and verifier-aligned schema check (hard completion gate)
- Save the workbook to the task-specified output path.
- Existence/readability check: confirm the output file exists at that exact path and can be reopened.
- Run the discovered recalculation/error scan tool on the saved output.
- If the tool returns JSON, parse it and validate required keys/types at minimum: status (string), total_errors (integer), and (when present) error_summary structure.
- Require: status indicates success AND total_errors == 0 before claiming completion.
- Bounded fallback if the primary tool fails:
- Inspect the error; choose one alternative verification route (LibreOffice headless if script missing; otherwise a library-based scan for error literals in cell values after recalculation attempt).
- Re-run only the smallest necessary check (recalc + error count) after each fix; avoid iterative broad changes.

## Constraints / Pitfalls
- Never replace a required workbook computation with a hardcoded numeric constant when the task restricts computation to Excel/spreadsheet formulas; if a function is unsupported, rewrite the formula using a compatible equivalent rather than hardcoding.
- Never implement "latest value" by hardcoding row/column indices; always use a dynamic last-nonblank or date-keyed lookup pattern, and verify it still works after recalculation.