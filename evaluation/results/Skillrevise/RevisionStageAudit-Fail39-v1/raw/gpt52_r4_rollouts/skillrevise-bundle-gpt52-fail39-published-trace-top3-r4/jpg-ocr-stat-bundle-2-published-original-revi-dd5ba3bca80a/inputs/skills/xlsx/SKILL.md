# OCR_to_XLSX_Extraction

## Purpose
Extract structured fields from images or PDFs using environment-available OCR, normalize them to a strict tabular schema, and write a verifier-aligned Excel (or CSV) artifact with post-write read-back validation to prevent silent content mismatches.

## When to Use
Use when the user needs OCR or document parsing (images/PDF pages) converted into a table (Excel/CSV) with exact headers, row rules, and strict formatting (for example, date and amount fields) where correctness depends on matching extracted values rather than spreadsheet formulas or modeling.

## Procedure
- 1) Preflight and requirement capture (no installs yet)
- Identify inputs: discover files by user-provided paths; if unspecified, list the working directory and ask for the exact input set.
- Identify required output: confirm required format (xlsx/csv), required sheet name(s), exact headers/order, sort order, and any formatting rules (date format, decimals, blank handling). If any are ambiguous, ask before extraction.
- Tool discovery anchor:
- Check OCR availability without changing the environment: verify whether a system OCR binary exists (for example, `tesseract --version`) and whether Python libraries needed for writing output are importable (for example, `python -c "import openpyxl"`).
- Record which route is feasible (system OCR + Python, or alternate route).
- 2) Choose extraction route (decision point, bounded fallbacks)
- Preferred: use available OCR binary/library already installed.
- If a planned tool is missing or fails:
- Fallback A (bounded): switch to an alternative already present (for example, different OCR CLI, OS-provided text extraction, or existing Python OCR bindings).
- Fallback B (bounded): if and only if the task requires a missing Python package and installs are blocked (PEP 668/external management), create and use a virtual environment for this run, then rerun only the smallest import check to confirm availability.
- If no OCR route is available, stop and request user guidance (allowed tools, providing pre-extracted text, or relaxing constraints).
- 3) Extract text per document with traceability
- For each input file, produce a per-file text representation (in memory or saved alongside outputs only if allowed) and keep a mapping from file name to extracted text.
- Capture minimal provenance needed for debugging: which engine was used, and any per-file warnings/errors.
- 4) Parse required fields with defensive heuristics
- Implement field parsing rules based on task-declared schema:
- Dates: parse using explicit patterns; normalize to the required output format; if multiple candidates exist, apply deterministic selection rules (for example, prefer labeled date fields over incidental dates).
- Totals/amounts: locate candidate lines using inclusion keywords (for example, "total") and exclusion keywords (for example, "subtotal", "tax") only if specified; otherwise keep heuristics minimal and deterministic.
- For each field, attach an internal confidence signal (for example, parse success boolean, number of candidates, or regex match quality) to drive validation and spot checks.
- 5) Build the output table and write artifact
- Create rows with stable keys (for example, filename) and normalize all fields to the required string/number formats.
- Write to the required artifact type:
- If xlsx: create exactly the required sheet name(s) and headers; avoid formulas unless explicitly requested.
- If csv/tsv: ensure delimiter and quoting match requirements.
- Apply required ordering (for example, sorted by filename) only if specified.
- 6) Post-write validation (schema and content) before claiming completion (execution anchor)
- Reload the produced artifact from disk and assert:
- Headers match exactly (names and order).
- Sheet name(s) match exactly (for xlsx).
- Row count matches requirements (or matches number of inputs if that is the stated rule).
- Field-level format checks:
- Date fields: all non-empty values parse to the required format; count parse failures.
- Amount fields: all non-empty values parse as numbers; enforce required decimals/normalization rules if stated.
- Sanity checks to prevent false certainty:
- Report null/empty rate per required field.
- List a small, bounded set of suspicious rows (for example, rows with missing totals, multiple date candidates, or parse failures) for review.
- If any assertion fails, do not finalize; return to parsing/extraction adjustments and rerun validation.

## Constraints / Pitfalls
- Do not attempt `pip install` or environment changes before running tool discovery; if installs are required and the environment is externally managed, use a bounded venv fallback or switch to already-installed tools instead of repeated install attempts.
- Do not claim success based only on file existence, sheet count, or row count; you must reload the output and validate headers and field formats, and you must surface a bounded anomaly report (parse failures/nulls/outliers) to avoid silent OCR mismatches.