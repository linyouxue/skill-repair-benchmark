# Tabular QA Analytics (Spreadsheet or CSV)

## Purpose
Answer quantitative questions from existing spreadsheet-like datasets by (1) discovering the actual table structure, (2) validating completeness and invariants, (3) computing the requested metric without inventing unstated rules, and (4) writing verifier-aligned outputs with explicit final checks.

## When to Use
Use when the task is to compute or verify a numeric/text result from an existing .xlsx/.csv/.tsv (or similar) dataset, especially when the dataset encodes repeated events (turns, rounds, transactions) where completeness per entity matters and missing/duplicate records could change the answer.

## Procedure
- 1) Establish the observable contract (before reading data)
- Identify: required input file(s), required output artifact path(s) and format (eg, single number, JSON, table), and any task-provided rules (scoring, ties, missing data, dedupe).
- If any of these are not explicit, mark them as unknown and plan to discover from files; do not guess.
- 2) Discover the environment and locate inputs
- List the working directory and search for candidate inputs by extension/name patterns.
- If multiple candidate files exist, open minimally (metadata/sheet names/header rows) to select the one that matches the task description.
- Do not hard-code paths; use paths discovered in the environment or provided by the task.
- 3) Load data with structure discovery (no assumptions)
- For spreadsheets: enumerate sheet names; for each candidate sheet, preview header rows and infer the actual header line.
- For delimited files: detect delimiter and encoding if unclear.
- Build a "data dictionary" from observed columns (names, types, example values) and map them to the task concepts (eg, game_id, turn, player/team, score/outcome).
- 4) Validate inputs and invariants (gating checkpoint; fail closed)
- Define required keys and invariants from the task text or from explicit dataset fields (examples: unique (game_id, turn, player), turn is integer range, expected number of turns per game if specified).
- Produce an integrity report that includes:
- Required columns present/missing
- Missing-value counts for required columns
- Duplicate counts for key fields
- Group-size distribution for the completeness unit (eg, turns per game, rows per match)
- If any invariant needed for correctness fails (missing rows, uneven group sizes, duplicates on key, impossible values), do not compute a single final answer yet. Proceed to step 5.
- 5) Bounded recovery for integrity failures (one short branch, evidence-based)
- Inspect the failure signal and attempt the smallest supported fix, in this order:
- Re-read with corrected header/sheet/range selection (common cause of "missing rows").
- Check for alternate sheets/hidden filters/merged header rows that shift data.
- If duplicates exist, dedupe only when the dataset provides an explicit rule (eg, identical rows, timestamp preference). Otherwise keep both and flag ambiguity.
- If records are missing: only impute if the task or source documentation explicitly defines the missing-data policy. If not defined, do not silently impute.
- If still ambiguous, compute separate results for each clearly plausible interpretation that is directly supported by observed fields (eg, "drop incomplete games" vs "treat missing as zero" only if either is stated). Do not choose among variants without textual justification.
- 6) Compute the requested metric with traceable logic
- Implement computation directly from validated fields; keep the mapping from dataset columns to task concepts explicit.
- Add internal cross-checks that should always hold (eg, recompute totals two ways, verify counts, verify outcomes match aggregated scores).
- If the task requires a single scalar, ensure the final value is derived from a fully validated dataset or from an explicitly justified policy.
- 7) Deliver output in the verifier-visible location (final checkpoint)
- Determine the required output path from the task/verifier text; if none is specified, write to the default only if the platform standard is known in-context; otherwise, ask or choose the minimal non-destructive action (eg, print result) rather than writing to an arbitrary path.
- Write exactly the required format (eg, a single number and newline, or strict JSON).
- Execution anchor: verify the artifact at the exact required path by an existence/readability check and a readback that matches the required format.

## Constraints / Pitfalls
- Never introduce special-case rules (ties, missing turns, incomplete games, imputation, dedupe) unless they are explicitly stated in the task text, source documentation, or unambiguously encoded in dataset fields; otherwise stop, ask for clarification, or compute and report multiple variants without selecting one.
- Do not hard-code sheet names, column letters, row counts, or expected group sizes unless they are verified invariants in the current input; always discover first and gate computation on the integrity report passing.