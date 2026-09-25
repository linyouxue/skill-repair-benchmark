# 13F Filer and Holding Analysis (Discovery-First)

## Purpose
Provide a reusable, environment-agnostic workflow to identify 13F filers and issuers from quarterly datasets (even with noisy names) and compute common downstream metrics (AUM, holding counts, quarter-to-quarter deltas, and holder rankings) with explicit discovery and schema validation checkpoints.

## When to Use
Use when a task references SEC 13F quarterly data (one or more quarter folders) and requires any combination of: (a) finding the correct filer from an approximate manager name, (b) mapping issuer name to CUSIP, or (c) computing metrics from 13F tables (AUM from summary pages, counts of holdings, VALUE-based deltas across quarters, or ranking filers by a position). Do not use if the task is unrelated to 13F data or already provides exact identifiers and no computations are needed.

## Procedure
- 1) Discover data roots and available tables (no hard-coded paths).
- If the user provides quarter directories, use them; otherwise discover likely roots by listing the working directory and common mounts (for example, the current dir and immediate subdirs).
- For each quarter directory, search for the key tables by pattern rather than fixed filenames:
- COVERPAGE (filer identity fields)
- SUMMARYPAGE (AUM/summary fields)
- INFOTABLE (holdings: issuer/CUSIP/VALUE/SHARES)
- Execution anchor (required): print the resolved file paths found for each table and print the header row (column names) for each file before proceeding.
- Decision: if any required table for the requested computation is missing, stop and request the missing location or switch to a computation that only uses available tables.
- 2) Load tables with schema validation and minimal normalization.
- Load using a general-purpose reader that matches the discovered format (TSV/CSV); do not assume delimiter until verified by inspecting the file (header and a couple lines).
- Validate required columns exist before using them:
- Filer identification typically needs an accession-like identifier plus name/address fields from COVERPAGE.
- AUM typically needs a numeric total from SUMMARYPAGE.
- Holdings computations need at least: accession identifier, CUSIP (or issuer identifier), and VALUE from INFOTABLE.
- Parse numeric fields defensively (strip commas/whitespace); fail fast if parsing yields mostly missing/NaN.
- Execution anchor (required): print row counts and a small sanity summary (for example, distinct accession count; min/max of VALUE if present). Branch/fail if tables are empty or columns missing.
- 3) Identify the correct filer (exact match first, then fuzzy with disambiguation).
- If an exact identifier is provided (accession/CIK/13F file number), filter by it and verify exactly one (or a clearly best) match.
- Otherwise fuzzy-match on normalized names:
- Normalize: lowercase, collapse whitespace, remove punctuation-only differences.
- Retrieve top K candidates with scores, but do not auto-select if the top scores are close.
- Disambiguate using additional constraints when provided (city/state, filing number, founder facts, etc.) by checking those fields in COVERPAGE rather than guessing.
- Decision: if ambiguity remains (top candidates within a small score band or conflicting constraints), stop and present the candidate list and what extra info is needed to choose.
- 4) Compute requested 13F metrics with cross-checks.
- AUM extraction: read the SUMMARYPAGE row(s) for the chosen accession and extract the declared total; record the units as stated by the dataset (do not assume dollars vs thousands without evidence).
- Holding count: in INFOTABLE filtered to the accession, count distinct holdings using a stable key (CUSIP preferred); define whether duplicates are possible and deduplicate explicitly.
- Quarter-to-quarter deltas: for two quarters, resolve the same filer across quarters using identifiers (preferred) or validated name+address matching; compute per-CUSIP VALUE differences after aligning units and types.
- Rank holders of a target CUSIP: for a given quarter, filter INFOTABLE by CUSIP and aggregate VALUE by accession/filer, then sort descending; verify that the CUSIP exists in the table before ranking.
- Final checkpoint: re-run a minimal verification on the computed outputs (non-empty results, expected keys present, and totals plausible relative to raw VALUE ranges). If any check fails, return to step 1/2 to re-verify paths, delimiters, and columns.

## Constraints / Pitfalls
- Never hard-code repo-specific scripts, flags, quarter labels, or absolute paths. Always discover files and verify headers before running any parsing or computation.
- Do not assume units for VALUE or AUM. Only label/convert units when the dataset explicitly indicates them; otherwise keep values in raw reported units and state that explicitly in downstream computations.