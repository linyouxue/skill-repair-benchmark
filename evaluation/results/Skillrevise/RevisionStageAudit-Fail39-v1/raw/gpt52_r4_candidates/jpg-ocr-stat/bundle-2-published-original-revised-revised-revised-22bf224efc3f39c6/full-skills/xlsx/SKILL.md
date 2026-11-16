# OCR_Receipt_To_Tabular_OracleAligned (Trace-Gated, No Uncontracted Heuristics)

## Purpose
Extract contract-specified fields from receipt-like images/PDFs into a tabular artifact that matches an oracle-style verifier by (1) enforcing contract-driven parsing only, (2) recording traceable evidence for every chosen value, and (3) blocking completion unless both schema and trace-backed semantic checks pass after reload.

## When to Use
Use only when the task provides (or you can discover from visible instructions/files) a fixed output artifact requirement (exact path, format, columns/order, row rule) and the grader/verifier likely checks exact extracted values (oracle comparison), not just that a spreadsheet exists.

## Procedure
- 1) Extract the observable contract (fail closed)
- From the task text, collect only what is explicitly specified or visible: required output path, file format (CSV/XLSX), required columns and order, row identity rule, null rules, and per-field selection rules (include labels, exclusion labels, next-line allowance, tie-break rules, normalization formats).
- If any of these are required to write the output but are missing or contradictory (especially output path, columns/order, row rule, null representation), stop and request clarification; do not invent defaults.
- 2) Discover inputs and tools (no installs; no hard-coded routes)
- Enumerate candidate input documents from task-provided locations; if none are specified, list files in the working directory and select only receipt-like extensions (e.g., PDF, PNG, JPG) without guessing hidden paths.
- Discover available extraction/writing tools by minimal checks (examples: can you import a PDF/text library; can you read images; can you write CSV/XLSX). Choose a primary extractor and exactly one fallback extractor that is already available.
- 3) Extract text per file with a bounded fallback and evidence retention
- For each input file:
- Run the primary extraction route and store raw extracted text plus extractor name.
- Quality check: if text is empty or extremely low-signal (very low alphanumeric density), run the single fallback route once and keep the better text (define "better" by higher alphanumeric count and presence of any contract include labels).
- Do not write any final artifact yet.
- 4) Contract-driven parsing only (no uncontracted heuristics) + TRACE GATE (execution anchor)
- For each file and each required field:
- Apply the contract rules as an ordered decision list:
- Candidate generation: only lines that match contract include labels/keywords for that field are eligible. If the contract defines priority groups, enforce them in order.
- Exclusions: drop any candidate lines matching any contract exclusion terms.
- Value location: only use same-line or next-line if the contract explicitly permits it; otherwise do not look at adjacent lines.
- Tie-break: apply only the contract tie-break. If none is specified, treat multiple remaining candidates as ambiguous (do not guess); set field to null.
- Parsing/normalization: only normalize formats explicitly required (e.g., date format, decimals). If parsing is ambiguous (e.g., dd/mm vs mm/dd) and the contract does not define the disambiguation, set null.
- Record a selection trace for every field, including:
- chosen_line_index (or "none"), include_label_hit (or "none"), exclusion_hit (true/false),
- used_next_line (true/false), tie_break_used (name or "none"),
- ambiguity_flag (true/false), and a short snippet of the chosen source line(s).
- Compute an anomaly summary across files (counts and rates):
- null_rate per field, ambiguity_count, next_line_count, and any selections made from low-priority/broad labels (only if the contract defines label priorities).
- Blocking rule (must pass before writing final output):
- If any field value is non-null but has no trace, stop.
- If any value required an ambiguity decision not specified by contract, force that value to null (do not guess) and mark ambiguous in trace.
- If anomaly summary indicates widespread ambiguity or unexpectedly high null rate relative to available label hits (visible from traces), loop back to step 2-4 (adjust extractor choice or tighten contract rules). Do not claim completion.
- 5) Write the artifact exactly to the contract path (no extras)
- Verify the parent directory of the required output path exists and is writable.
- Write exactly the required columns in the required order; do not add extra sheets, columns, formatting, or derived values unless required.
- Apply the contract null representation precisely (blank cell vs empty string vs explicit token only if contract says so).
- 6) Reload-and-assert schema and trace-backed semantics (execution anchor)
- Re-open the written artifact from the exact required output path and assert:
- File exists and is readable at that path.
- Headers match exactly (names and order) and sheet name constraints if specified.
- Row count and row key rule match the contract.
- Null serialization round-trips as required (null stays null on reload; not "NA"/"null"/empty-string unless specified).
- For each non-null field value, confirm there is a recorded trace for that row/field and that the value meets declared normalization/parsing rules.
- If any assertion fails, do not finalize; return to step 2-5 and correct the root cause (extraction route, rule application, writer behavior).

## Constraints / Pitfalls
- Do not introduce or rely on uncontracted heuristics (examples: defaulting dd/mm vs mm/dd, early-exit OCR thresholds, broad keyword expansion like matching "AMOUNT" as "TOTAL"). If the contract does not specify a disambiguation or label set, treat it as ambiguity and output null with a trace.
- Do not claim success from schema/format checks alone. Completion requires (1) trace gate pass before writing and (2) post-write reload assertions that include trace-backed semantic validity, not just headers and regex formatting.