# xlsx-template-fill

## Purpose
Reusable workflow for filling an existing .xlsx template with values and formulas sourced from external datasets (e.g., macro series) and for computing derived quantities inside the workbook using Excel formulas, then recalculating and verifying with headless LibreOffice.

## When to Use
Use when the task supplies an existing target .xlsx and asks you to populate specific cells or ranges from named external data sources (PWT, IMF WEO, ECB SDMX, World Bank, etc.) and/or to compute transforms (growth rates, filters, smoothers) that must live as formulas in the workbook. Do not use for free-form spreadsheet creation, pure data analysis, or tasks requiring interactive Excel Solver.

## Procedure
- Discover: locate the task-specified workbook path; open with `openpyxl.load_workbook(path)`; print `wb.sheetnames` and inspect existing headers, year rows, and any pre-filled formulas. Record the exact cells, ranges, and units the task names. Never create new sheets or overwrite existing formulas unless the task says so.
- Acquire data: for each required series, use discovery not hard-coded URLs. Try the documented primary route, bound retries to <=3 attempts, then switch to a fallback. Examples of route families (verify current endpoints at run time):
- PWT: Dataverse datafile endpoint referenced from the GGDC PWT page; fallback to the GGDC page's current download link.
- IMF WEO: bulk `WEO<Mon><Year>all.ashx` under the WEO Database release path; fallback to DataMapper API or per-indicator CSV.
- ECB: SDMX REST `data-api.ecb.europa.eu/service/data/{flow}/{key}?format=csvdata`; fallback to the dataset's bulk CSV. Cache responses locally; align on country code and year before any write.
- Write: with openpyxl, write raw inputs as values at the exact cells the task specifies, matching units and year columns. Prefer cross-sheet references (`='Inputs'!B5`) over duplicating data. Use formulas for every derived quantity (sums, ratios, growth, logs). Do not hardcode computed numbers.
- Derived transforms without Solver: implement filters and smoothers as closed-form matrix formulas. For HP filter, build the (I + lambda * K'K)^{-1} y expression using `MMULT`, `MINVERSE`, and `TRANSPOSE` over a helper range holding the second-difference matrix K; lambda lives in a single labeled input cell. If a task strictly requires Solver, flag it as interactive-only and still provide the closed-form formula result as the delivered value.
- Recalc and verify: save, then run `python recalc.py <path>` and parse its JSON. Require `status == "success"` and `total_errors == 0`. If errors are reported, fix the referenced cells and recalc again. Finally re-open the saved file and assert the target path exists, the named cells are non-empty, and spot-check 2-3 formula outputs against an independent computation.

## Constraints / Pitfalls
- Write only to cells the task specifies; preserve all existing formulas, formatting, named ranges, and sheet order.
- No hardcoded calculated values in cells: every derived number must be an Excel formula referencing inputs.
- Bound each external fetch to <=3 attempts before switching to a fallback route; stop URL enumeration once any supported route returns data.
- Headless LibreOffice cannot execute Solver or VBA; replace optimization steps with closed-form formulas or precomputed weights expressed as formulas.
- Verify year and country-code alignment before bulk-filling a range; off-by-one on the year axis is the most common silent failure.
- Final acceptance requires: file exists at the task-specified path, `recalc.py` reports zero formula errors, and target cells are populated.