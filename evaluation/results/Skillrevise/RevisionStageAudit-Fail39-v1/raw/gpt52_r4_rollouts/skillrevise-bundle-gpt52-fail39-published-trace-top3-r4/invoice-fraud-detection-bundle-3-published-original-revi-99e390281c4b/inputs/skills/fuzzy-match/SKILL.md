# Fuzzy Matching for Entity Reconciliation (Fraud-Safe)

## Purpose
Provide a deterministic, fraud-safe procedure for reconciling noisy entity strings (e.g., vendor names, payees) to a reference registry using normalization plus fuzzy matching, with explicit ambiguity handling and post-result validation.

## When to Use
Use only when the task requires linking records across datasets where at least one join key is a human-entered string (names, free-text identifiers) and exact matching is insufficient. Do not use if the task already has stable unique IDs for joining, or if the task is end-to-end document parsing/detection without an explicit reconciliation step.

## Procedure
- Step 1: Confirm matching contract and inputs
- Identify: (a) query strings to match, (b) reference candidate set, (c) what constitutes an acceptable match, and (d) the required output format (JSON fields, file path, or stdout). If any are unspecified, ask or infer minimally and record assumptions.
- Refuse irreversible actions (writes/overwrites) until the output destination and schema are known or explicitly optional.
- Step 2: Discover environment and choose match engine (execution anchor)
- In Python, probe dependencies in order:
- Try `import rapidfuzz` (preferred). If it fails, fall back to stdlib `difflib`.
- Do not assume external CLI tools exist (e.g., `file`, `pdftotext`). Prefer pure-Python checks and imports; if a tool is needed, first verify availability and provide an alternate path.
- Step 3: Normalize consistently (apply to both query and reference)
- Apply the same normalization pipeline everywhere:
- lowercase
- strip/normalize whitespace
- remove punctuation (keep alphanumerics and spaces)
- optional: expand/standardize common business tokens (inc, ltd, corp) only if it improves recall and does not merge distinct entities in your domain
- Keep the original raw string alongside normalized form for traceability.
- Step 4: Generate candidates and score with guardrails
- Hard constraints before fuzzy matching:
- If there is a strong identifier (vendor_id, tax_id, IBAN, registration number), use it as a blocking key; do not fuzzy-match across conflicting strong IDs.
- If the normalized query is empty or too short, return UNKNOWN (no match) rather than guessing.
- Scoring:
- Use a single, documented similarity metric (rapidfuzz ratio/WRatio, or difflib ratio).
- Rank candidates and compute: best_score and runner_up_score.
- Decision policy (deterministic):
- MATCH only if best_score >= threshold AND (best_score - runner_up_score) >= margin.
- AMBIGUOUS if best_score >= threshold but margin is too small (near-tie) or multiple candidates are effectively equivalent.
- UNKNOWN if best_score < threshold or required blocking constraints fail.
- Record evidence per decision: chosen_candidate_id (if any), best_score, runner_up_score, metric_name, engine_name, and the normalization used.
- Step 5: Finalize output and validate (execution anchor)
- Produce outputs in the task-required channel (file path or stdout). If a path is specified by the task/verifier, write exactly there and then check readability.
- Validate by reloading the produced artifact (or validating the in-memory object) and asserting:
- Required keys exist (at minimum: query, decision, and either matched_id or reason).
- Types are correct (strings/nums/arrays as required).
- Invariants hold: decision is one of MATCH/AMBIGUOUS/UNKNOWN; scores are within the metric range; MATCH implies matched_id present; UNKNOWN implies no matched_id.
- If validation fails, do not guess; fix the producing step and re-validate.

## Constraints / Pitfalls
- Never auto-match when a strong identifier conflicts (e.g., different vendor IDs, tax IDs, IBANs). In such cases return AMBIGUOUS/UNKNOWN and require human review or additional evidence.
- Avoid brittle tooling assumptions: do not require installing packages or using non-guaranteed CLI utilities. Always probe availability and keep a stdlib fallback, even if it is slower.