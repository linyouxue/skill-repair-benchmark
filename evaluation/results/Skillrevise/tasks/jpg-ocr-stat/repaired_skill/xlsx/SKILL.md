# OCR_Receipt_To_Tabular_OracleAligned

## Purpose
Extract specific fields (for example, date and total) from receipt-like images or PDFs using available OCR/text extraction, apply deterministic include/exclude selection rules, and write a verifier-aligned tabular artifact (XLSX/CSV) with strict read-back checks that prevent silent semantic and null-representation mismatches.

## When to Use
Use when a task provides fixed inputs (a set of document files) and a fixed tabular contract (exact output path, columns, and per-field extraction rules), and success depends on matching an external oracle/verifier rather than producing a merely well-formed spreadsheet.

## Procedure
- 1) Contract and environment discovery (fail closed before doing work)
- Read the task instruction and extract only the observable contract: required output path, file format (xlsx/csv), required columns and order, row key rule (often filename), and explicit field rules (include keywords, exclusion keywords, next-line rules, tie-breakers, and null-on-failure requirement).
- Discover inputs from provided paths; if not explicitly listed, list candidate files in the working directory and select only the task-relevant extensions (images/PDF) without guessing hidden locations.
- Tool discovery (no installs): confirm available extractors/writers by running minimal checks (for example: OCR CLI version, Python imports for imaging/OCR and xlsx/csv writing). Record the chosen primary route.
- 2) Output path grounding (do not write elsewhere)
- Use the exact task-specified output path. If it is missing from instructions, stop and request it (do not invent /output, ./, or a filename).
- Before writing, verify the parent directory exists and is writable; if not, stop and report what is missing (permissions/mount/path).
- 3) Per-file text extraction with a bounded fallback
- For each input file:
- Extract text with the primary available route.
- Minimal quality check: if extracted text is empty or clearly low-signal (for example, too few alphanumeric characters), retry once with one alternate already-available route (for example, alternate OCR binding, PDF text extraction if PDF, or different OCR mode) and keep the better result.
- Store: extracted text, and which extractor was used. Do not proceed with irreversible writing yet.
- 4) Deterministic field parsing with semantic traceability (execution anchor)
- For each required field, implement the task-declared rules as an ordered decision list (do not add extra heuristics that are not in the contract):
- Include-keyword scan: find candidate lines containing required include keywords for that field.
- Exclusion filter: drop candidates containing any exclusion keywords for that field.
- Next-line rule: if the contract allows "value on next line", apply it only when the include-keyword line has no parseable value and the next line does.
- Tie-break: if multiple candidates remain, apply only the stated tie-breaker (for example, first occurrence, closest to label, or highest numeric magnitude only if specified). If tie-break is unspecified, choose a deterministic default (first occurrence) and flag it as ambiguous.
- Parsing: normalize date/amount formats exactly as required. If parsing fails, set the value to null per contract.
- Emit a bounded selection trace per file and per field (store internally and print a small sample): chosen rule path (keyword_hit/next_line/ambiguous/fail), the include keyword hit (if any), whether any exclusion was encountered, and a short raw snippet around the chosen source. This is a checkpoint: if many rows are ambiguous or rely on fallbacks, adjust parsing before writing.
- 5) Build rows and write the artifact exactly to the contract
- Create one row per input per the contract (or the contract-defined row rule), using the required row key.
- Enforce null semantics: when the contract says null on failure, write a true null (blank cell in XLSX, empty field in CSV only if the verifier expects that; otherwise stop and clarify).
- Write XLSX/CSV with exact column headers and order; do not add extra sheets, formulas, styling, or derived columns unless required.
- 6) Post-write verifier-aligned reload and schema enforcement (execution anchor)
- Re-open the written artifact from the exact required output path and assert:
- File exists and is readable at that path.
- Headers match exactly (names and order) and required sheet name(s) match if XLSX.
- Row keys match the contract rule (for example, exact filenames) and row count matches the rule.
- Null representation check: cells that should be null reload as None/blank (not empty string or a placeholder like "NA").
- Date/amount normalization check: all non-null dates parse to the required format; all non-null amounts satisfy numeric/decimal rules exactly as required.
- Produce a bounded anomaly report (for example, top 5 rows) driven by the selection traces: missing keyword hits, excluded-line selections, ambiguous ties, parse failures, or unusually high null rate. If any contract assertion fails, stop and return to steps 3-5; do not claim completion.

## Constraints / Pitfalls
- Do not ask clarifying questions when the task contract is already explicit; instead, execute deterministically. Only stop to ask when a required output path/schema/rule is genuinely missing or contradictory.
- Do not claim success based on file existence or header checks alone. You must (a) ground the output at the exact required path, (b) enforce null serialization semantics via reload, and (c) provide semantic selection traces plus a bounded anomaly report to catch oracle-sensitive extraction mismatches before finalizing.