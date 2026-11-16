# xlsx

## Purpose
Create, edit, analyze, and recalculate `.xlsx` workbooks, including workbooks embedded inside container formats (`.pptx`, `.docx`, `.xlsm`, other OOXML zips). Ensure formulas are preserved and cached formula results are refreshed so downstream readers (including verifiers using `data_only=True`) see current values.

## When to Use
Trigger whenever the task involves reading, writing, or modifying spreadsheet content in OOXML/`.xlsx` form, either as a standalone file or as an embedded part inside another OOXML container. Also trigger when a task edits inputs that feed Excel formulas and the deliverable will be read for calculated values. Do not trigger for pure CSV/TSV text transforms with no formulas and no container.

## Procedure
- Classify the input:
- Standalone workbook: path ends in `.xlsx`/`.xlsm` and is a valid zip whose top-level members are `[Content_Types].xml`, `xl/`, etc. Use the standalone branch.
- Container with embedded workbook: path ends in `.pptx`/`.docx`/`.xlsm` (or similar) and contains members matching `*/embeddings/*.xlsx` (discover via `zipfile.ZipFile(path).namelist()`; typical globs: `ppt/embeddings/*.xlsx`, `xl/embeddings/*.xlsx`, `word/embeddings/*.xlsx`). Use the container branch.
- Validate tooling before irreversible writes:
- Confirm `openpyxl` import works.
- Confirm `recalc.py` is present and `python recalc.py --help` or a dry run succeeds; LibreOffice must be callable. If missing, stop and report; do not substitute Python-computed values for formulas.
- Standalone branch: a. Load with `openpyxl.load_workbook(path)` (keep formulas; do not use `data_only=True` when you intend to save). b. Edit cells. Prefer Excel formulas over Python-computed constants for any derived value. c. Save to the target path. d. If the workbook contains any formulas, run `python recalc.py <path>` and parse the returned JSON. Require `status == "success"` and `total_errors == 0`; otherwise fix references and re-run. e. Verify: reopen with `load_workbook(path, data_only=True)` and confirm formula cells return non-None values consistent with edited inputs (structural check, not hardcoded expected numbers).
- Container branch (xlsx embedded in pptx/docx/other OOXML): a. Create a working directory. Extract only the target embedded member(s) discovered in step 1; remember each member's `ZipInfo` from the original archive. b. Edit the extracted `.xlsx` using the standalone branch steps 3a-3c. c. Run `python recalc.py <extracted_embedded.xlsx>`. Require `status == "success"` and `total_errors == 0`. This step is mandatory whenever formulas exist in the embedded workbook, even if only inputs were changed. d. Reopen the extracted embedded file with `load_workbook(..., data_only=True)` and assert formula cells now hold refreshed values (non-None, and changed relative to pre-edit snapshot when inputs changed). e. Repackage the container: open the original archive and a new output archive; for every entry, if it is the edited embedded member, write the new bytes using the original `ZipInfo` (preserve `filename`, `compress_type`, `date_time`, `external_attr`); otherwise copy the original bytes unchanged. f. Sanity-check the output: it opens as a zip, `namelist()` matches the source, and the embedded member round-trips through `load_workbook(..., data_only=True)` with refreshed values.
- Error handling and fallback:
- If `recalc.py` reports formula errors (`#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#N/A`), use the JSON `error_summary` locations to repair references, then recalc again. Do not ship a file with formula errors.
- If LibreOffice/`recalc.py` is unavailable, stop and surface the limitation; do not replace formulas with Python-computed literals as a workaround.
- If embedding discovery finds multiple candidate `.xlsx` members, select by matching the member whose sheet/cell layout contains the cells the task references; if ambiguous, report and ask.

## Constraints / Pitfalls
- Never replace a formula cell with a Python-computed constant to "fix" stale values; always recalc.
- Never modify zip members other than the targeted embedded workbook; preserve original `ZipInfo` metadata (compression, timestamps, attributes) for all untouched members.
- Never save a workbook that was loaded with `data_only=True`; this discards formulas.
- Recalculation is mandatory whenever formulas exist, including embedded workbooks whose inputs were changed, before repackaging the container.
- Do not hardcode container member paths; discover them via `zipfile.ZipFile(...).namelist()` and glob patterns such as `*/embeddings/*.xlsx`.
- Keep cell references explicit and avoid off-by-one errors; Excel rows/cols are 1-indexed while pandas is 0-indexed.
- For reading-only analysis, prefer `pandas.read_excel` or `load_workbook(..., data_only=True, read_only=True)`; for editing, use `openpyxl` without `data_only`.
- Do not add formatting, color, or number-format conventions unless the task or an existing template requires them; match existing template styling when editing in place.