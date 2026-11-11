# 13F TSV Quarter Dataset Analyzer (Semantics-Gated)

## Purpose
Analyze SEC 13F TSV exports organized by quarter folders to compute fund-level summaries, quarter-over-quarter holding changes, and cross-fund holders for a CUSIP, while preventing false certainty by requiring evidence-backed semantic mapping (field meaning and units) and unambiguous identifier resolution before producing final outputs.

## When to Use
Use this when you are given one or more quarter directories containing TSV files (commonly COVERPAGE.tsv, SUMMARYPAGE.tsv, INFOTABLE.tsv) and the task asks for metrics keyed by a manager/filing (accession) and/or an issuer security identifier (CUSIP), potentially requiring a verifier-checked JSON artifact.

## Procedure
- 1) Discover the environment and inputs (checkpoint: files are real and readable).
- List the available quarter directories in the current workspace; do not assume names or paths.
- For each quarter you will use, locate required TSVs by discovery (at minimum: COVERPAGE, SUMMARYPAGE, INFOTABLE if the task needs both fund totals and holdings).
- Evidence gate: for each TSV you rely on, confirm it exists and is readable (non-empty, can read first line).
- 2) Inspect schemas from the actual TSV headers (checkpoint: column mapping is evidence-based).
- Read the header row for each TSV and record the exact column names you will use.
- Build a column map (your internal names -> observed header names). If a required concept is not present, stop and re-scope (do not guess a column).
- Evidence gate: print/record the chosen columns for accession id, report period/date, CUSIP, value, and any issuer/title/class fields you plan to use.
- 3) Semantic mapping and unit confirmation (checkpoint: task term -> dataset field + unit is proven).
- Identify every task term that implies a definition/unit (examples: "AUM", "total value", "market value", "value", "shares").
- Search local documentation in the provided environment (README, data dictionary/codebook, comments, or accompanying notes) for:
- The meaning of the candidate SUMMARYPAGE total field(s) and the INFOTABLE value field.
- The unit convention (eg, dollars vs thousands) and any rounding/scaling notes.
- Decision point:
- If you can cite local evidence mapping the task term to a specific field and unit, proceed using that field and explicitly carry the unit in your reasoning/output.
- If you cannot confirm the mapping/unit from local evidence, stop and request clarification (or, if the task explicitly instructs an assumption, apply only that stated assumption and label it).
- Evidence gate: record file names and the exact matching lines that justify the mapping/unit, or record that no confirming evidence was found and halt.
- 4) Identify the correct filing/accession per quarter (checkpoint: accession is validated across files).
- From COVERPAGE, search for the manager/fund name from the task and produce a ranked candidate list with the columns available to disambiguate (eg, manager name, report period/date, report type).
- Apply tie-break rules using only observed columns (eg, matching report period to the quarter folder; correct report type if present).
- Decision point: if multiple candidates remain close/ambiguous, require explicit selection; do not silently choose.
- Validate the selected accession by confirming it appears in SUMMARYPAGE and has non-zero holdings rows in INFOTABLE for that quarter.
- Evidence gate: show the selected accession and the row counts found in SUMMARYPAGE and INFOTABLE.
- 5) Resolve issuer-to-CUSIP deterministically (checkpoint: CUSIP selection is unique or explicitly chosen).
- When the task requires "find the CUSIP for <issuer>", first enumerate candidates:
- Filter INFOTABLE by issuer/name match using the observed name/title fields (if present); if no name field exists, you cannot do issuer lookup from INFOTABLE alone and must use another provided mapping or ask for clarification.
- List distinct candidate CUSIPs with counts and any available descriptors (title/class/ticker if present).
- Decision point:
- If exactly one plausible CUSIP remains after checking descriptors and consistency, select it.
- If multiple plausible CUSIPs remain, do not select by frequency; require explicit selection criteria from the task or stop for clarification.
- Evidence gate: output the candidate CUSIP list and the rule/evidence used to select (or the reason you halted).
- 6) Compute requested aggregates and changes with recomputable definitions (checkpoint: numbers can be re-derived).
- Single-quarter fund summary:
- Compute the requested total (only after step 3 confirms definition/unit) from SUMMARYPAGE for the accession.
- Compute holdings count with an explicit definition (eg, distinct CUSIP count vs total rows) and report both if helpful for verification.
- Quarter-over-quarter changes:
- Repeat accession identification for each quarter.
- Aggregate holdings by CUSIP within each quarter (sum value per CUSIP), then join and compute signed deltas.
- Apply the task-required ranking rule (signed vs absolute) explicitly.
- Cross-fund holders for a CUSIP:
- Filter INFOTABLE by the validated CUSIP (from step 5), group by accession, sum value, rank, and map accession -> manager name via COVERPAGE.
- Evidence gate: verify the join completeness (no unexpected missing manager names for ranked accessions).
- 7) Write outputs and verify path + JSON schema (checkpoint: artifact exists, reloads, and matches requirements).
- Determine required output path strictly from task instructions; if none is provided, pause and search the environment for a convention (eg, existing answer template) before choosing.
- Write JSON atomically, then:
- Confirm the file exists at the required path and is readable.
- Reopen and JSON-parse it.
- Validate required keys/types/shapes derived from the prompt or a provided template (do not invent fields).
- Validate numeric fields are finite numbers (not NaN/inf) and that lists/objects have consistent element structure.
- If any check fails, fix and re-run the write+reload+validate loop; do not declare completion without passing.

## Constraints / Pitfalls
- Never emit a precise "AUM/total value" number unless you have local, environment-provided evidence for (a) which dataset field corresponds to the requested concept and (b) the unit/scaling; otherwise stop for clarification rather than guessing.
- Never auto-select a CUSIP (or accession) by frequency or convenience when multiple plausible candidates exist; enumerate candidates with evidence and require an explicit disambiguation rule or user selection before proceeding.