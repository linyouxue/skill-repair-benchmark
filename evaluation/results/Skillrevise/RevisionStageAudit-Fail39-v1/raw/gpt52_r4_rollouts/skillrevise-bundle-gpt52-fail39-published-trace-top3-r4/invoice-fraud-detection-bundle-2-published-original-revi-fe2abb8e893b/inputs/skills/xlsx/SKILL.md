# Verifier-Aligned Document And Reference-Table Fraud Report To JSON

## Purpose
Produce a deterministic JSON fraud/validation report by extracting records from semi-structured documents (often PDFs) and validating them against structured reference tables (CSV/XLSX), while strictly aligning outputs to the verifier-visible contract (path, schema, enumerations, and conventions) and avoiding invented heuristics.

## When to Use
Use when a task requires joining document-extracted records (invoices/payments/forms) to reference tables and emitting a machine-checked JSON file. Do not use if the required output path or JSON schema/conventions cannot be discovered from task instructions, repository files, or tests.

## Procedure
- 1) Discover the verifier-visible contract (gatekeeper step).
- Locate and record: required output path, JSON schema (required keys, types, nullability), allowed fraud reason strings (enum), record inclusion convention (only flagged vs all), and reason convention (single reason vs list; first-applicable vs all-applicable; ordering).
- Sources (in order): task instructions, README, schema files, sample outputs, and tests.
- Decision point: If any required contract element is unknown, stop and request clarification (do not guess thresholds, enums, or shapes).
- 2) Validate environment and inputs using library-first probing (no brittle OS assumptions).
- Enumerate candidate input files from provided paths or current working directory; for each, assert it exists and is non-empty.
- Probe parseability by attempting to open with appropriate libraries (PDF reader, CSV reader, XLSX reader). Treat missing optional OS tools (for example `file`) as non-fatal if library parsing succeeds; if parsing fails, stop and report the exact file and error.
- For reference tables: read header(s) and validate required columns per contract; read identifier-like columns as strings.
- 3) Extract, match, and apply rules deterministically (no invented fuzzy thresholds).
- Extraction: for each document record, capture only contract-required fields plus internal provenance needed to debug rule triggers (for example, page index if required by contract).
- Matching: perform staged matching with collision-safe handling (do not collapse multiple candidates into one by normalized key).
- Allowed matching operations are only those stated or inferable from provided examples/tests (for example, exact match on ID; exact match on normalized text).
- Decision point (fuzzy matching): If the task says fuzzy matching is allowed but provides no method and no acceptance criterion (threshold/top-k/tie-break), do not introduce a numeric cutoff. Either:
- restrict to exact/normalized-exact matching and mark unresolved matches as unknown/ambiguous if the schema supports it, or
- stop for clarification if a vendor/PO resolution is required to produce valid output.
- Rules: implement in the exact priority order from the contract. Enforce the contract convention:
- If "first applicable only": emit exactly one reason for each flagged record (the first triggered).
- If "all applicable": emit a stable ordered list (rule order), no duplicates.
- Missing/ambiguous fields: do not silently assume values. Only treat missing data as a rule trigger if the contract explicitly says so; otherwise produce unknown/needs-review if representable, or stop if output cannot be made contract-compliant.
- 4) Write output to the contract path and run a verifier-aligned audit before finalizing (execution anchor).
- Write JSON to the exact required output path (do not silently switch directories or paths).
- Assert the file exists and is readable at that exact path.
- Reload the JSON and validate:
- Schema: required top-level keys and per-record keys exist; types and nullability match; arrays/objects have the correct shape (single vs list).
- Enumerations and conventions: fraud reasons (if present) are exactly from the allowed set; first-applicable vs all-applicable behavior holds (for example, reasons length equals 1 when required); inclusion convention holds (only flagged vs all).
- Determinism checks: ordering is stable if the contract demands it (for example, sorted by record id or page).
- Decision point: If any audit check fails, do not claim completion. Fix the minimal upstream step (contract extraction, parsing, matching, rule logic, serialization) and re-run the audit until all checks pass.

## Constraints / Pitfalls
- Never invent fuzzy matching thresholds, tie margins, or scoring rules. If the contract does not specify the method and acceptance criteria, either avoid fuzzy matching (and mark unresolved as unknown/ambiguous if allowed) or stop for clarification.
- Do not rely on non-portable OS utilities for core validation (for example `file`). Use library-based open/parse attempts with explicit error handling; treat missing tools as a fallback trigger, not a reason to guess or proceed blindly.