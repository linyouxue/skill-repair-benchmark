# xlsx

## Purpose
Create, edit, and analyze .xlsx workbooks so that formulas are preserved, recalculated under the available spreadsheet engine, and validated for both syntactic (no formula errors) and semantic (plausible numeric outputs, documented data selections) correctness.

## When to Use
Use when the task requires producing or modifying an .xlsx workbook whose cells contain formulas that must recalculate correctly, or when analytical outputs must be derived from multi-sheet source data. Do not load this skill for pure CSV/TSV transforms, pure data extraction without formulas, or tasks where no .xlsx artifact is produced.

## Procedure
- Discover inputs: list sheet names and column headers for every source workbook with openpyxl or `pandas.read_excel(sheet_name=None)`; record which sheet and column supplies each required quantity before writing any formula.
- Define conventions explicitly: in a Notes or Assumptions cell, write the exact definitions used (return type, window length, horizon, confidence level, units) and the entity-reconciliation rule across sheets (e.g., inner join on normalized country name; log any excluded entity with the reason).
- Validate environment: write one probe cell per non-trivial function family you plan to use (statistical, lookup, text). Run `python recalc.py <file>` and inspect the JSON. If `#NAME?` appears, substitute a LibreOffice-safe equivalent (e.g., `NORMSINV` instead of `NORM.S.INV`, `STDEV` instead of `STDEV.S`, `INDEX`+`MATCH` instead of `XLOOKUP`) and record the substitution in Notes. Never hardcode a statistical constant to bypass a function error without a comment stating the source and value.
- Build with formulas, not Python-computed values: use cell references for every derived quantity so the model recomputes when inputs change. Place assumptions in named cells and reference them.
- Recalculate: run `python recalc.py <file>` and confirm `status: success` and `total_errors: 0`. If errors remain, fix at the referenced cell addresses and repeat.
- Verify outputs semantically: reload with `load_workbook(path, data_only=True)` in a throwaway check (do not save), and assert for each declared output cell that it is non-empty, numeric where expected, and within a sanity-bound range documented in an adjacent comment. Log any entity exclusions, missing-data substitutions, or constant hardcodes to a Notes sheet.
- Recover: if a verification assertion fails, trace back to the discovery or convention step that produced the wrong input selection; do not patch by overwriting the output cell with a literal.

## Constraints / Pitfalls
- Zero formula errors is necessary but not sufficient; a workbook can pass `recalc.py` and still be semantically wrong. Always run the semantic self-check.
- Never save a workbook that was opened with `data_only=True`; formulas will be lost.
- Do not silently drop rows, countries, tickers, or periods due to missing data. Record the exclusion rule and the excluded keys in a Notes sheet.
- Do not hardcode statistical constants (z-scores, critical values) or lookup results to work around an unsupported function unless a comment states the source, numeric value, and the function it replaces.
- Prefer broadly supported functions (`NORMSINV`, `STDEV`, `AVERAGE`, `INDEX`, `MATCH`, `SUMPRODUCT`) over Excel-only variants when the recalculation engine is LibreOffice.
- Do not import financial-model color-coding, template-preservation, or number-format conventions unless the user or an existing template explicitly requires them; they add context without aiding correctness.