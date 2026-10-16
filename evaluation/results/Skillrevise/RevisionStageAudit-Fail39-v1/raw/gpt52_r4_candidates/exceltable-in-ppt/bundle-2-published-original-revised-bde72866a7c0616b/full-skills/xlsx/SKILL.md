# XLSX and Embedded OOXML Spreadsheet Editing (Python-first)

## Purpose
Create, read, modify, and validate spreadsheet files (xlsx/xlsm/csv/tsv) and spreadsheets embedded inside OOXML containers (for example, pptx with embedded workbooks) using environment-safe, dependency-light workflows that preserve formulas and formatting.

## When to Use
Use this skill when the task requires programmatic spreadsheet edits (values, formulas, sheets, basic formatting) or when a spreadsheet is embedded inside a zip-based OOXML file (pptx/docx/xlsx) and must be updated without relying on system tools like unzip or root package installs. Do not use this skill for pure chart redesign in PowerPoint unless it explicitly depends on editing embedded workbook data.

## Procedure
- 1) Preflight and discovery (before any write)
- Confirm the target file(s) exist and are readable; identify the user-required output location (if unspecified, ask).
- Execution anchor: in one shell command, probe that the input is a zip-based OOXML container:
- `python -c "import sys,zipfile; p=sys.argv[1]; print('is_zip', zipfile.is_zipfile(p))" <path>`
- If `is_zip` is False, stop and ask whether the file is the correct input (or whether it is password-protected/corrupt).
- Check Python libraries: try importing `openpyxl`; if missing, plan a CSV-based edit only if the user confirms the output may be downgraded to CSV (otherwise stop and request an allowed tool).
- 2) Choose the minimal tool route (decision point)
- If editing a standalone xlsx/xlsm: use openpyxl for cell edits, formulas, and light formatting.
- If editing an embedded workbook inside pptx/docx (OOXML container):
- Prefer Python `zipfile` to inspect and extract only the needed members.
- Discover likely embedded workbooks by listing members and focusing on:
- `ppt/embeddings/` (PowerPoint)
- `word/embeddings/` (Word)
- Any member ending in `.xlsx` or `.xlsm` inside the container
- If no candidate embedded workbook is found, stop and ask for clarification (the deck may link externally or use chart caches instead of embeddings).
- 3) Edit workbook content safely (no irreversible actions yet)
- For each target workbook:
- Load with openpyxl without `data_only=True` to avoid destroying formulas on save.
- Make the smallest required changes:
- Prefer writing Excel formulas (strings beginning with `=`) rather than computed Python values when the user expects a dynamic spreadsheet.
- Preserve existing sheet names, structure, and cell formats unless the user explicitly requests changes.
- Validate edits locally:
- Re-open the saved workbook and spot-check a few edited cells for expected formulas/values presence (not calculated results).
- Scan formulas you touched for obvious divide-by-zero or missing references (lightweight checks; do not assume a full recalc engine exists).
- 4) Repack and verify (bounded checks, then finalize)
- If editing an OOXML container (pptx/docx):
- Write a new output file rather than modifying in place unless the user requests in-place edits.
- Replace only the edited embedded member(s) in the zip, leaving all other members untouched.
- Execution anchor: verify the output is a valid zip and still contains expected structure:
- `python -c "import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); print('members',len(z.namelist())); print('has_embeddings',any(n.startswith('ppt/embeddings/') for n in z.namelist()))" <output>`
- If any verification fails (cannot open zip, missing members, missing embeddings unexpectedly), stop and revert to the last known-good artifact; re-run only the smallest failing check after adjusting the approach.

## Constraints / Pitfalls
- Never attempt system package installs (apt-get, brew, yum) or assume tools like unzip/LibreOffice exist unless you have explicit permission and have verified they are available and usable in the environment. Default to pure-Python (`zipfile`, `openpyxl`) methods.
- Do not save workbooks loaded with `data_only=True`; it can permanently replace formulas with values. Preserve formulas by loading normally and only writing the minimal required cells.
- Shell interface constraint: issue single-command executions or explicitly chain within one command using `&&` or `;` (do not rely on multi-command submissions being accepted).
- Do not hard-code container member paths; always discover members via zip listing first, then operate only on confirmed matches.