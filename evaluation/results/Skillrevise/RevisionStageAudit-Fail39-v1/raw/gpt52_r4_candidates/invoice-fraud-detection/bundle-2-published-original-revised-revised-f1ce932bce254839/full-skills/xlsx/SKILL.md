# Deterministic Document And Reference-Table Fraud Report To Verifier-Aligned JSON

## Purpose
Create a reusable, deterministic workflow to extract records from semi-structured documents (often PDFs) and validate them against structured reference tables (CSV/XLSX), applying explicitly ordered fraud/validation rules and emitting a JSON report that matches the task-declared schema and verifier conventions.

## When to Use
Use when a task requires (1) reading document records (invoices, payments, forms) from PDFs or similar, (2) joining/validating against a vendor/PO/reference table, and (3) producing a machine-checked JSON output. Use only when the task provides (or you can discover) the required output path and the rule semantics; otherwise stop for clarification.

## Procedure
- 1) Extract the verifier-visible contract before any implementation decisions.
- Locate from task instructions and repository/starter assets (README, schema files, tests, sample outputs):
- Required output path(s).
- Required JSON schema (required keys, types, optional fields, allowed nulls).
- Content conventions: only flagged records vs all records; one reason (first-applicable) vs multiple reasons; required rule priority order; page indexing (0-based vs 1-based).
- Checkpoint: If any of the above is not discoverable, do not invent it; request clarification and list the unknowns.
- 2) Discover environment and validate inputs (readability and parseability) using non-brittle probing.
- Enumerate candidate input files from provided paths or current working directory; verify each is present and non-empty.
- Open each input with a library-based reader (preferred) and extract minimal evidence:
- PDF: confirm at least one page can be text-extracted (or detect it is image-only and require OCR availability).
- XLSX: list sheet names and read header row(s).
- CSV/TSV: read header row and a small sample; confirm delimiter.
- Decision point: If a file cannot be parsed, stop and report the exact failing file and error; do not proceed with partial guesses.
- 3) Load reference tables with explicit column validation and stable key handling (no lossy normalization maps).
- Read IDs and codes as strings (PO/invoice/vendor IDs often have leading zeros).
- Validate required columns exist per the discovered contract; if missing, stop and ask for the correct mapping.
- Normalize for matching using a two-track approach:
- Keep raw values for output and audit.
- Create normalized values for matching, but never use a normalized string as a unique dictionary key that can overwrite collisions; store lists of candidates per normalized form or match directly over the full candidate set.
- 4) Extract document records with deterministic parsing and explicit unknown handling.
- For each record, capture the fields required by the schema, plus minimal provenance (e.g., source page number if required).
- For each parsed field, store:
- raw_text (as extracted),
- parsed_value (or null),
- parse_status (e.g., parsed, missing, ambiguous, unparseable) if the schema allows, otherwise keep it internal.
- Decision point: For any field needed to evaluate rules, if it is missing/ambiguous/unparseable, do not silently pass; follow the contract if specified, else mark the record as requiring clarification or apply the least-committal behavior (do not introduce a fraud reason that depends on unknown data unless the contract explicitly says missing triggers a reason).
- 5) Implement matching and fraud rules without invented constants; make ambiguity explicit.
- Vendor (or entity) matching staged strategy:
- Exact match on raw values when possible (including exact ID matches if present).
- Exact match on normalized values (case/whitespace/punctuation normalization) with collision-safe handling:
- If multiple reference rows match equally, treat as ambiguous.
- Fuzzy matching only if the contract specifies the method AND acceptance criterion (threshold or top-k rule). If not specified:
- Do not introduce a numeric threshold.
- Either (a) skip fuzzy matching and treat non-exact as unknown, or (b) produce an explicit ambiguity/needs-review outcome if the schema/rules support it; otherwise stop for clarification.
- Apply rules in the exact discovered priority order.
- If the contract says "first applicable reason only", then for each record:
- evaluate rules in order and emit exactly one reason (the first that triggers).
- do not append additional reasons.
- If the contract says "all applicable reasons", emit a stable, ordered list (rule order) with no duplicates.
- Checkpoint: Ensure rule logic does not depend on unstated defaults for missing values; every missing-data branch must be tied to a contract statement or handled as unknown/clarification.
- 6) Write output to the required path and run a contract check harness before claiming completion (execution anchor).
- Write JSON to the exact required output path from the contract step (do not change directories silently).
- Reload the JSON you wrote and assert:
- It parses.
- Top-level and per-item keys/types match the discovered schema (including nullability and required arrays/objects).
- Content constraints match conventions:
- only-flagged vs all-records behavior,
- first-applicable-only vs multi-reason behavior (e.g., assert reasons length equals 1 when required),
- stable ordering constraints if specified (e.g., by record id or page).
- Matching sanity checks using data-driven probes:
- Identify a small set of records where vendor names/IDs appear to exactly match reference entries; assert they resolve as known (or as the contract expects).
- Assert there are no collision-induced nondeterministic outcomes (same input should produce same match across runs).
- Decision point: If any assertion fails, fix the minimal upstream step (contract extraction, parsing, matching, rule implementation, serialization) and re-run the harness; do not state completion until the harness passes.

## Constraints / Pitfalls
- Do not invent thresholds, scoring cutoffs, or fuzzy-match acceptance criteria. Only use them if explicitly present in task instructions, schema, tests, or provided examples; otherwise treat fuzzy matching as unsupported and escalate for clarification.
- Do not use lossy normalization mappings that overwrite candidates (e.g., dict keyed by normalized name to a single vendor). Always preserve all candidates and handle ties/ambiguity deterministically per the contract.