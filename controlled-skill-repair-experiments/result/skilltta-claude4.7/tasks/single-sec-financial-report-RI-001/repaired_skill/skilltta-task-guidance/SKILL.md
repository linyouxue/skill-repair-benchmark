---
name: skilltta-task-guidance
description: Temporary guidance for analyzing SEC 13F hedge fund filings across Q2/Q3 2025 datasets, with emphasis on verifying helper-script paths before invocation.
---

# Task Guidance: 13F Hedge Fund Q2→Q3 Comparison

## Context
You are comparing 13F filings between `/root/2025-q2` and `/root/2025-q3`. The data is typically a set of TSV/SQLite tables (COVERPAGE, SUBMISSION, INFOTABLE, etc.). You must produce `/root/answers.json`.

Two relevant skills exist in the environment:
- `13f-analyzer/SKILL.md`
- `fuzzy-name-search/SKILL.md`

**The location hint explicitly flags that the helper-script invocation paths and path conventions in these two SKILL.md files may be wrong.** Do NOT trust the documented commands blindly.

## Mandatory First Step: Verify Skill Paths
Before running any helper command from either skill:
1. `ls` the skill directory (e.g. `ls -la <skills_root>/13f-analyzer/` and `.../fuzzy-name-search/`) to see what scripts actually exist.
2. Open `SKILL.md` and read the documented command, then compare with the real script filename and location.
3. If the SKILL.md says e.g. `python scripts/foo.py ...` but the file is at `./foo.py` or `bin/foo.py`, adjust the invocation. Common fixes:
   - Wrong relative directory (`scripts/` vs root of skill)
   - Wrong dataset path argument (needs absolute `/root/2025-q2`, not a default)
   - Needing to `cd` into the skill directory first, or conversely needing to run from `/root`.
4. Patch the SKILL.md call site in your plan (do not necessarily edit the file; just use the corrected command).

## Workflow Per Question

### Q1 – Renaissance Technologies AUM (Q3)
1. Use fuzzy-name-search skill on COVERPAGE in `/root/2025-q3` with term `"renaissance technologies"`. Pick highest-score match → `accession_number`.
2. Use 13f-analyzer to pull fund detail for that accession → extract AUM (likely sum of `VALUE` in INFOTABLE, or a reported AUM field; follow the skill's documented aggregation). Return as a number.

### Q2 – Number of stocks held by Renaissance (Q3)
Using the same accession from Q1, count distinct holdings. Prefer counting rows in INFOTABLE for that accession (or distinct CUSIPs — read the skill's convention; typically it is row count of positions). Return integer.

### Q3 – Berkshire Hathaway top-5 CUSIP increases Q2→Q3
1. Fuzzy-search COVERPAGE in both `/root/2025-q2` and `/root/2025-q3` for `"berkshire hathaway"`. Keep the Buffett entity (Berkshire Hathaway Inc, Omaha) — disambiguate if multiple hits by picking the one with largest portfolio / matching filer name.
2. Load INFOTABLE holdings for each accession.
3. Join on CUSIP; compute `delta_value = value_q3 - value_q2` (treat missing Q2 as 0 — these are new positions and count as increases).
4. Sort descending by `delta_value`, take top 5 CUSIPs. Return as list in that order.

### Q4 – Top-3 managers holding Palantir by share value in Q3
1. Find Palantir's CUSIP. Approach: search INFOTABLE for issuer name containing `PALANTIR` across Q3 dataset and inspect the dominant CUSIP (Palantir Technologies Class A — commonly `69608A108`). Verify empirically from the data, do not hardcode.
2. Filter all Q3 INFOTABLE rows with that CUSIP, group by accession_number, sum `VALUE`.
3. Join with COVERPAGE/SUBMISSION on accession_number to get filer/manager NAME.
4. Sort descending by summed value, take top 3 manager names. Return as list.

## Output
Write exactly:
```json
{
  "q1_answer": <number>,
  "q2_answer": <number>,
  "q3_answer": ["...","...","...","...","..."],
  "q4_answer": ["...","...","..."]
}
```
to `/root/answers.json`. Numbers must be bare JSON numbers (not strings).

## Patterns Borrowed From Reference Solutions
- **SQLite + pandas** (ref: BigCodeBench/408): if the 13F data is in SQLite, use
  ```python
  import sqlite3, pandas as pd
  with sqlite3.connect(db_file) as conn:
      df = pd.read_sql_query(query, conn)
  ```
  This is the cleanest way to run joins/aggregations for Q3 and Q4.
- **CSV/TSV ingestion with explicit schema** (ref: BigCodeBench/784): if data is TSV, read with `pd.read_csv(path, sep='\t', dtype=str)` then coerce numeric columns (`VALUE`, `SSHPRNAMT`) with `pd.to_numeric(..., errors='coerce')` before summing.
- **Robust file loading with existence checks** (ref: BigCodeBench/381): before each step, assert the file/dir exists; drop NaN rows on key columns (CUSIP, VALUE) to avoid groupby surprises; wrap in try/except to surface the real error path, which is especially useful when the skill helper scripts have broken paths.

## Defensive Tips
- Dollar values in 13F are typically reported in thousands — be consistent across Q2 and Q3 (both will use same unit, so deltas are fine without unit conversion). For Q1 AUM, report in the same unit the 13f-analyzer skill returns; if ambiguous, prefer raw dollars (×1000).
- When fuzzy matching, lowercase and strip punctuation. If the fuzzy-name-search script errors out, fall back to a direct SQL `LIKE '%RENAISSANCE%TECH%'` or pandas `str.contains` query on COVERPAGE.NAME.
- Berkshire often has multiple filings per quarter (amendments). Prefer the latest/largest filing per quarter; if two accessions, pick the one whose INFOTABLE sum is largest (the primary 13F-HR).
- Always print intermediate results (accession numbers, row counts, top-10 before truncating to top-5/3) so a reviewer can audit the chain.
