# Excel Workbook with External Data and Scenario Modeling

## Purpose
Deliver an Excel workbook that ingests external statistical or macro-economic series, links them across sheets with formulas, and replicates scenario or assumption tables so that all computed cells are formula-driven and re-run when inputs change.

## When to Use
Trigger when a task asks for an .xlsx deliverable that must (a) pull data from external sources (official statistics agencies, IMF/World Bank style databases, provided CSVs), (b) link multiple sheets, and (c) express scenarios or assumptions as parameters. Do not trigger for pure data-cleaning, pure plotting, or generic spreadsheet formatting tasks; in those cases use a plain pandas/openpyxl approach.

## Procedure
- Inspect inputs first: list any provided template file, required sheet names, target cells, named assumptions, exchange rates, and multipliers. Preserve existing sheet names and layout exactly; do not re-style a template that already has conventions.
- Plan data sources before fetching: for each required series, write a one-line source plan with primary route (documented bulk download URL or official API with query pattern) and one fallback (manual download placeholder cell, user-supplied file path, or latest-known cached file). Cap endpoint discovery at a small number of failed attempts (e.g., 5) before switching to the fallback.
- Acquire data via the chosen route. If the fallback is used, place the raw figures in a clearly labeled Inputs/Raw sheet with a source note cell (source, date, URL or filename) so they are treated as inputs, not calculations.
- Populate the workbook with formulas only for computed cells: cross-sheet links as `=Sheet!Cell`, aggregations via SUM/AVERAGE/INDEX/MATCH, and scenario outputs that reference parameter cells (growth rate, FX rate, multiplier) rather than embedding constants in formulas. Script tooling (e.g., openpyxl) may write the formula strings, but must not pre-compute and hardcode numeric results.
- Verify: open the saved file (or recalculate via LibreOffice if the environment supports it), spot-check 2-3 target cells to confirm they contain formulas and resolve to sensible values, and confirm that changing a parameter cell propagates through dependent cells.

## Constraints / Pitfalls
- Excel-only semantics: every computed cell must be an Excel formula; never write Python-computed numeric constants into cells that the task defines as calculations.
- Bounded fallback is mandatory: if the primary data route fails repeatedly, switch to the documented fallback and label placeholder inputs clearly; do not keep retrying endpoint discovery.
- Keep assumptions in dedicated parameter cells and reference them with absolute references (e.g., `$B$3`); do not inline rates or multipliers in formulas.
- Preserve existing template structure, sheet names, and ordering; add new sheets only when the task cannot be satisfied in-place.
- Do not import unrelated formatting conventions (color codes, number masks) unless the task or template explicitly requires them.