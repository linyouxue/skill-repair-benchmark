# multi-source-reconciliation

## Purpose
Reusable workflow for reconciling records across heterogeneous sources (e.g., PDF, XLSX, CSV) under a task-declared set of flag rules with explicit precedence. The skill enforces field-parse validation, discovery-driven matching, and distribution sanity checks before any report is finalized. Generic fuzzy-string tricks are a last-resort fallback, not the headline technique.

## When to Use
Trigger when the task requires joining or flagging records from multiple source formats under a declared rule list (fraud detection, invoice audit, dataset consolidation, entity resolution with ordered reasons) and the verifier scores a structured report. Do not trigger for pure one-to-one string similarity tasks where no rule precedence or multi-source parsing is involved.

## Procedure
- Discover contract: read the task statement and list (a) all source files and their formats, (b) the exact set of flag rules and their declared precedence order, (c) the required output schema. Restate precedence in your working notes verbatim; do not infer or reorder.
- Discover identifier schemes: inspect 3-5 raw records per source to learn the vendor/entity id pattern (e.g., `Vendor <N>` vs free-text company names), amount format (currency symbol, decimal separator, thousands separator), and date format. Record these as discovered invariants.
- Validate-on-sample checkpoint: fully parse one known-good record end to end and print extracted fields. Confirm by eye that vendor id, amount (as numeric), date, and any join keys match the raw source. Do not proceed to batch parsing until this passes.
- Build matching strategy from discovery: use exact normalized lookup first (lowercase, trim, collapse whitespace). Only fall back to fuzzy matching when (i) exact lookup fails and (ii) the candidate pool is small enough that false matches are unlikely. For short structured ids like `Vendor 1` vs `Vendor 11`, prefer exact or token-equality matching over ratio-based fuzz; ratio-based scorers are unsafe on short numeric suffixes.
- Apply flag rules in declared precedence: for each record, evaluate rules in order and assign the first matching reason. When two rules both apply to the same record, record both in a debug log so the precedence choice can be audited.
- Self-verify checkpoint: compute the distribution of assigned reasons across the full output. If any single reason exceeds a plausibility ceiling (e.g., >40% of records) or if a reason you expected to see is absent, halt and re-check 2-3 representative rows against the raw sources. Confirm the parse, not just the rule evaluation.
- Schema-check the output: reload the written report and assert required columns, types, and value domains match the task-declared output schema before claiming completion.

## Constraints / Pitfalls
- Do not hard-code rule precedence, thresholds, or vendor-id regexes; derive them from the task statement and discovery each run.
- Do not apply ratio-based fuzzy matching to short structured identifiers (e.g., `Vendor <N>`); use exact or tokenized equality.
- Do not accept a dominant failure reason without re-verifying field parsing on affected rows; a skewed distribution is a signal, not a conclusion.
- Do not treat generic company-suffix normalization (`inc`, `ltd`, `corp`) as default; apply only if discovery shows free-text company names in the data.
- Do not finalize before the validate-on-sample and self-verify checkpoints have produced observable evidence (printed fields, printed distribution summary).
- If a required tool (PDF parser, spreadsheet reader) is unavailable, stop and report the missing dependency rather than silently skipping records.