# Document And Tabular Fraud-Check Report (PDF/CSV/XLSX to JSON)

## Purpose
Create a deterministic pipeline to ingest semi-structured documents (often PDFs) plus structured reference data (CSV/XLSX/TSV), extract required fields, apply ordered fraud/validation rules, and emit a verifier-aligned JSON report with strict schema and path checks.

## When to Use
Use when the task requires reading invoices/records from PDFs or other documents, joining or validating against vendor/PO/reference tables, and producing a machine-checked JSON (or similar) report of only flagged items. Do not use for spreadsheet modeling, formatting, or formula recalculation tasks.

## Procedure
- 1) Confirm inputs and required outputs before processing (no assumptions).
- Identify: input document paths, reference table paths, and the exact required output path and JSON schema from task instructions or starter files.
- If any of these are ambiguous, stop and request clarification rather than guessing field names, rule order, or output location.
- 2) Discover the environment and verify files are readable (bounded fallback if tools missing).
- Prefer listing directory contents with minimal flags and reading via language libraries rather than relying on optional CLI tools.
- If a planned CLI tool is missing or errors (example: `file` not found), fall back once to a Python-based check:
- Confirm the file exists, is non-empty, detect type by magic bytes (e.g., %PDF, ZIP container), and attempt to open:
- PDF: open and read at least 1 page text.
- XLSX: load workbook and read sheet names.
- CSV/TSV: read header row and row count.
- Decision point: If a file cannot be opened/read, do not proceed; report the failing path and error and ask for a replacement or tool constraint.
- 3) Load reference tables with explicit schemas and normalize join keys.
- Read CSV/XLSX with explicit dtype choices for IDs (treat PO numbers, invoice IDs, vendor IDs as strings).
- Normalize for matching: trim whitespace, normalize case, standardize punctuation, and keep the original raw values for reporting.
- Decision point: If required columns are missing, stop and ask which columns map to required fields; do not invent mappings.
- 4) Extract document records with page anchoring and field-level confidence.
- Extract per page (or per record boundary), capturing at minimum the task-required fields and the page index used by the verifier (confirm whether 1-based or 0-based; default only if explicitly stated).
- For each extracted field, keep: raw text, parsed value, and a minimal confidence signal (e.g., exact match vs heuristic).
- Decision point: If extraction yields multiple candidates for a required field, pick deterministically (documented tie-break) or mark as ambiguous and treat as a rule trigger if the task defines that.
- 5) Apply fraud/validation rules in required priority order and record reasons deterministically.
- Implement rules exactly in the order specified by the task; if no order is given, define and document one order and keep it consistent.
- For each invoice/record, accumulate reasons as a list of stable string labels (no free-form prose unless the schema requires details).
- Strictly output only flagged items (those with at least one reason), unless the task explicitly requires all items with a flagged boolean.
- 6) Write the output artifact, then validate path and schema before finalizing (execution anchor).
- Write JSON to the exact task-required output path (do not silently change directories).
- Post-write checks:
- File exists and is readable at that path.
- JSON parses successfully.
- Schema assertions: required top-level keys exist; types match (object/array/string/number); each flagged item has required fields and a non-empty reasons list; no unflagged items are present if the contract says "only flagged".
- If any check fails, fix the minimal upstream step (parsing, matching, rule application, serialization) and re-run the post-write validation.

## Constraints / Pitfalls
- Do not hard-code paths, sheet names, column names, rule thresholds, or page indexing; discover from inputs/task instructions and validate before processing.
- Do not rely on optional shell tools; if a command fails, use one bounded fallback (Python/library-based) and then stop for clarification rather than iterative guessing.