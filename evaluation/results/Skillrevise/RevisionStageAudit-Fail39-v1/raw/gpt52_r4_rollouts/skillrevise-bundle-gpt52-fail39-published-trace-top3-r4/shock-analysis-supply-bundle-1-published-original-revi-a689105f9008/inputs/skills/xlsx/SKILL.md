# Excel-Only Workbook Update With Playwright UI Data Collection

## Purpose
Populate or update an existing spreadsheet using data collected from websites via browser UI automation, while respecting strict tool constraints (for example, Excel-only editing and Playwright-only web collection) and producing a verifier-visible updated workbook artifact.

## When to Use
Use when the user provides (or references) a spreadsheet to be filled/extended and either (a) requires edits to be performed in a spreadsheet UI (no Python/programmatic cell editing) and/or (b) requires web data to be collected via Playwright (UI navigation, export/download, or table capture). Do not use for tasks that explicitly allow/require programmatic spreadsheet editing (pandas/openpyxl) or where no web collection is needed.

## Procedure
- 1) Confirm constraints and deliverable
- Extract and restate: (a) input workbook location/name, (b) required output location/name (or required upload/download route), (c) forbidden tools (for example: no Python, no APIs), and (d) required web sources and fields (country, indicators, years).
- Decision point: If the user forbids a tool that would be required (for example, no browser automation but web data is required), stop and ask for an allowed alternative.
- 2) Workbook preflight discovery (no edits yet)
- Open the provided workbook in the allowed spreadsheet UI.
- Identify and record: sheet names, any existing tables, named ranges, and the exact target tabs/columns/rows to populate.
- Checkpoint: Verify the file is writable via the allowed route (save-as test if needed). If not writable, diagnose permissions/mounts and ask for a writable output path rather than switching silently.
- 3) Web data acquisition via Playwright MCP (bounded, UI-first)
- For each required dataset/source:
- Use Playwright to navigate to the official site UI, apply filters (for example: country, indicators, frequency, years), and attempt export/download (CSV/XLSX) using the site-provided controls.
- If export is not available, capture the visible table in a stable way (for example: copy table, download view, or structured scrape of the rendered table).
- Bounded fallback (avoid endpoint guessing loops):
- If two UI export attempts fail due to site errors, auth, or missing controls, switch once to an alternate UI path on the same site (for example: different download button or table view).
- If still blocked, stop and ask for one of: credentials, a permitted mirror link, a user-provided file export, or permission to use an API. Do not continue guessing undocumented endpoints.
- 4) Populate the workbook in Excel UI and save
- Import/paste the acquired data into the identified target ranges without changing unrelated formatting or structure unless the user requested it.
- Use spreadsheet formulas for computed fields (do not compute in external tools when Excel-only is required).
- Checkpoint: Spot-check a small set of cells per sheet (at least one per inserted table) to ensure values align with the source (country/indicator/year) and formulas reference the intended ranges.
- 5) Final artifact grounding and verification (must be verifier-visible)
- Save the workbook to the user-specified output path/name (or the platform-supported export/download route).
- Re-open the saved workbook and confirm:
- The expected sheets/ranges contain the new values/formulas.
- The file exists and is readable at the exact required path/route.
- If the file is missing or not readable at the required location, do not claim completion; inspect save location, permissions, and the platform export mechanism, then retry the minimal save step.

## Constraints / Pitfalls
- Do not use Python (pandas/openpyxl), LibreOffice recalc scripts, or API endpoint guessing when the user requires Excel-only edits and Playwright-only collection; violating tool constraints is a hard stop.
- Do not perform irreversible edits (bulk delete/overwrite, structural refactors) before completing workbook discovery and confirming the exact target ranges; always bound web-retrieval retries (max two attempts per UI path) to prevent iteration/timeouts.