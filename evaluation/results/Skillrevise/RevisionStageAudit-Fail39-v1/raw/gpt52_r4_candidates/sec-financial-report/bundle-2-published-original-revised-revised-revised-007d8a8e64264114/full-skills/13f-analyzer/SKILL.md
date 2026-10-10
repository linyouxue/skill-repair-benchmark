# 13F TSV Quarter Dataset Analyzer (Robust Preview + Output-Grounded)

## Purpose
Analyze SEC 13F TSV exports organized by quarter folders to compute fund- and holding-level summaries and produce a verifier-consumable JSON artifact, using discovery-based schema mapping, bounded fallbacks for preview/parsing, and strict output grounding to the task-required path.

## When to Use
Use this when you are given one or more directories of 13F TSV exports (for example, quarter folders containing files like COVERPAGE.tsv, SUMMARYPAGE.tsv, and INFOTABLE.tsv) and you must compute requested metrics and write a JSON result file that will be checked by an automated verifier.

## Procedure
- 1) Confirm the observable contract and inputs (checkpoint: you know what must be produced).
- Extract from the task prompt: required output path (if specified), required JSON keys, and any required numeric fields or ranking rules.
- Discover available data roots by listing the working directory; identify candidate quarter folders by inspection (do not assume names).
- For each quarter needed, locate TSVs by name pattern (case-insensitive contains COVERPAGE, SUMMARYPAGE, INFOTABLE) and confirm readability and non-empty size.
- 2) Discover TSV schemas with a bounded preview fallback (checkpoint: header names are observed, not guessed). (EXECUTION ANCHOR)
- For each required TSV, obtain headers and one sample row using this ladder, stopping at the first success:
- Method A (shell): print header and one row with tabs made visible:
- head -n 2 <file> | tr '\t' '|'
- If Method A fails or output is clearly not TSV-like, Method B (python): parse header safely:
- python -c "import csv,sys; p=sys.argv[1]; f=open(p,newline=''); r=csv.DictReader(f,delimiter='\t'); print('FIELDS', r.fieldnames); print('ROW', next(r,None))" <file>
- Build a column map from observed headers for: accession/filing id, report period/date, manager name, CUSIP, value, shares (if needed), and any issuer/title fields used for matching.
- Decision point: if a required concept has no corresponding observed column, stop and ask for clarification or adjust the requested metric (do not invent columns).
- 3) Select the filing/accession per quarter (checkpoint: accession is present across required tables).
- Using COVERPAGE, enumerate candidate accessions that match the requested manager/fund identifier (exact or normalized string match based on observed manager fields).
- Tie-break only using observed fields (for example, report period/date consistent with the quarter folder).
- Validate the chosen accession by checking it appears in SUMMARYPAGE (if needed) and has at least one matching row in INFOTABLE for that quarter.
- Decision point: if multiple candidates remain ambiguous, stop and request an explicit selection rule.
- 4) Resolve security identifiers (CUSIP) deterministically when required (checkpoint: unique or explicitly selected).
- If the task provides a CUSIP, use it directly after confirming it exists in INFOTABLE.
- If the task provides an issuer/name and asks you to find the CUSIP:
- Enumerate distinct candidate CUSIPs from INFOTABLE rows matching the issuer/name fields you observed.
- Decision point: if more than one plausible CUSIP remains after using available descriptors (title/class/ticker if present), stop and request disambiguation (do not choose by frequency).
- 5) Compute requested metrics with explicit definitions (checkpoint: recomputable and consistent joins).
- Compute aggregates only from columns you mapped in step 2.
- For quarter-over-quarter changes: aggregate per CUSIP within each quarter for the selected accession, then join and compute deltas per the task rule (signed vs absolute; ranking rule must match prompt).
- For cross-fund holders: filter by CUSIP, group by accession, aggregate value/shares as requested, then join to COVERPAGE to label manager names; verify ranked rows have manager labels (or report missing labels explicitly).
- 6) Write and verify the required JSON output (checkpoint: exists at required path, parseable, schema-valid). (EXECUTION ANCHOR)
- Determine the output path:
- If the task specifies a path, use it exactly (for example, /root/answers.json).
- If unspecified, pause and discover a repository convention (template file, instructions) before choosing a path.
- Write JSON atomically (write to a temporary file in the same directory, then rename).
- Immediately verify:
- File exists at the required path and is readable.
- JSON parses successfully.
- Schema validation: derive required keys/types/shapes from the task prompt or a provided template file (if present). Assert required keys exist and value types match (number/string/object/list); do not add extra required keys not stated.
- Fallback after write failure:
- If write or rename fails, inspect directory existence and permissions; create missing parent directories only if allowed by the environment and the required path implies they should exist; otherwise stop and report the permission/mount issue without switching to a different output path.

## Constraints / Pitfalls
- Do not use brittle text transforms for TSV inspection (for example, sed substitutions that assume a prior regex). Use the bounded preview ladder (tr or python csv) and stop only if both fail.
- Do not guess schemas, units, or identifiers: only compute from observed headers and prompt-declared rules; when multiple accessions or CUSIPs are plausible, enumerate candidates and require an explicit disambiguation rule rather than silently choosing.