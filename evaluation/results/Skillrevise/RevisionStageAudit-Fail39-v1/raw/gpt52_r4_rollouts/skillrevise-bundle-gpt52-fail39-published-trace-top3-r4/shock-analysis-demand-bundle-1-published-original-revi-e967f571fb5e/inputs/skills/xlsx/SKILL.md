# Excel-Only Spreadsheet Build and Repair (No-Python Mode)

## Purpose
Create, modify, and validate spreadsheets using an Excel-only workflow (no programmatic editing), with a focus on linking data, building scenario calculations, and delivering a workbook that recalculates cleanly with zero formula error values.

## When to Use
Use this skill when the task requires working in Excel (or an Excel-compatible UI) and either (a) the user explicitly forbids Python/programmatic edits, or (b) the environment does not support reliable spreadsheet scripting. Do not use this skill for pure data science pipelines where programmatic generation is allowed and preferred.

## Procedure
- Step 1: Intake and constraint gate (before touching files)
- Confirm: (a) "Excel-only" requirement (no Python/macros/scripts), (b) whether hardcoding calculated results is forbidden, (c) required sheets/cells/outputs and how many scenarios/variants are needed.
- If the task requires programmatic edits or you cannot access an Excel UI/editor, stop and request an alternate allowed method or a user-provided edited workbook.
- Step 2: Discover the workbook and map dependencies (in Excel)
- Open the workbook and inventory: sheet list, named ranges (if any), existing formulas vs inputs, and any template conventions already present.
- Identify the exact target areas: required sheets, specific cell ranges to populate, link, or scenario-toggle.
- Checkpoint evidence: you can point to the target sheets/ranges and understand which cells are inputs vs formulas/links (no edits yet).
- Step 3: Acquire required external inputs with bounded effort
- Prefer deterministic, official sources already specified by the task. If a download link or file is required but not provided:
- Attempt at most N=5 retrieval actions total (for example: open 1-2 official pages, try 1-2 obvious download buttons/links, search within the page for .xlsx/.csv).
- If still ambiguous, stop acquisition and request a user-provided direct file or URL, or permission to use a specific alternate source.
- Checkpoint evidence: the required input file(s) are present and openable in Excel, or you have an explicit user-approved fallback.
- Step 4: Edit and link (Excel-native; no calculated hardcodes)
- Make changes in this order to reduce breakage:
- Populate raw data tables (paste values only where the task expects source data, not where formulas should be).
- Create links/references from calculation sheets to data sheets (use cell references, structured references, or named ranges as appropriate).
- Implement scenario inputs as dedicated input cells and have scenario outputs reference those inputs.
- Decision point: If a value is derived, do not paste a computed number; instead, create an Excel formula or link that computes it from inputs.
- After each major block (data, then links, then scenarios), do a quick spot-check: open precedent/dependent tracing on a few key cells to confirm links point where intended.
- Step 5: Verify and finalize (mandatory)
- Force full recalculation in Excel (application recalculation / calculate workbook).
- Execution anchor: run workbook-wide Find for each error token (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?) and confirm no matches; if matches exist, navigate to each and fix root cause (bad references, missing inputs, divide-by-zero guards), then recalc and re-check.
- Save deliverable and re-open once to confirm formulas persist and results remain stable.

## Constraints / Pitfalls
- Do not run Python, openpyxl, pandas, LibreOffice recalc scripts, or any programmatic spreadsheet edit when the task/user says "Excel only" (treat this as a hard stop constraint).
- Do not hardcode derived/calculated outputs: if a cell is meant to be computed, implement an Excel formula or a link to source inputs. If the requirement is ambiguous (input vs computed), pause and ask before editing.