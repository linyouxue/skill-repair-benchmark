---
name: skilltta-task-guidance
description: Temporary guidance for analyzing 13F hedge-fund filings across Q2/Q3 2025 using the existing 13f-analyzer skill, with emphasis on correct per-quarter holding aggregation.
---

# SkillTTA Task Guidance: 13F Q2 vs Q3 2025 Analysis

## Goal
Answer four questions about hedge-fund 13F filings in `/root/2025-q2` and `/root/2025-q3`, writing results to `/root/answers.json` with keys `q1_answer` (number), `q2_answer` (number), `q3_answer` (list of 5 CUSIPs), `q4_answer` (list of 3 manager names).

## Reuse Pattern: Query-then-DataFrame (from BigCodeBench/408)
Treat each quarter's dataset as a SQLite-like store. The idiom:

```python
import sqlite3, pandas as pd
def q(db, sql, params=()):
    with sqlite3.connect(db) as c:
        return pd.read_sql_query(sql, c, params=params)
```

Use this uniformly for COVERPAGE lookup, SUMMARYPAGE/fund-detail lookup, and INFOTABLE holdings. Do not hand-roll parsing when a tabular query suffices.

## Workflow
1. **Locate the 13f-analyzer skill** (`13f-analyzer/SKILL.md`) and follow its documented loaders for each quarter.
2. **Fuzzy name search on COVERPAGE** (`FILINGMANAGER_NAME ILIKE '%renaissance technologies%'` or Python `rapidfuzz`) → choose the single best-match `ACCESSION_NUMBER` per quarter.
3. **Fund details** come from the SUMMARYPAGE / fund-detail table joined on `ACCESSION_NUMBER`:
   - AUM → `TABLEVALUETOTAL` (reported in **thousands USD** in raw 13F; confirm the skill's convention before multiplying).
   - Stock count → `TABLEENTRYTOTAL` **as reported on the summary page**, NOT a `COUNT(*)` or `COUNT(DISTINCT CUSIP)` over INFOTABLE rows. INFOTABLE rows are per-class/per-manager splits and will overcount.

### ⚠️ Critical caveat (per location hint)
The existing `13f-analyzer/SKILL.md` single-quarter holdings-aggregation step has an ambiguous "quantity unit" (口径). Before answering Q2:
- Verify whether "number of stocks held" means (a) `TABLEENTRYTOTAL` from SUMMARYPAGE, (b) `COUNT(DISTINCT CUSIP)` from INFOTABLE, or (c) raw `COUNT(*)` of INFOTABLE rows.
- The intended semantic for this task is **distinct issuer positions** → use `TABLEENTRYTOTAL` when available, else `SELECT COUNT(DISTINCT CUSIP) FROM INFOTABLE WHERE ACCESSION_NUMBER = ?`.
- If the skill currently returns raw INFOTABLE row counts, override it here. Record the chosen definition in a short comment next to the answer.

## Q3: Berkshire Hathaway holding deltas
1. Fuzzy-match "Berkshire Hathaway" in COVERPAGE for **both** quarters → two accession numbers (`acc_q2`, `acc_q3`).
2. Aggregate per CUSIP in each quarter:
   ```sql
   SELECT CUSIP, SUM(VALUE) AS val
   FROM INFOTABLE WHERE ACCESSION_NUMBER = ? GROUP BY CUSIP
   ```
   (13F VALUE is in thousands; units cancel for ranking.)
3. Full outer join on CUSIP, fill NaN with 0, compute `delta = val_q3 - val_q2`, keep `delta > 0`, sort desc, take top 5 CUSIPs.
4. New positions in Q3 (not present in Q2) are valid candidates — ensure the join preserves them.

## Q4: Palantir top-3 holders by share value in Q3
1. Find Palantir's CUSIP: search INFOTABLE for `NAMEOFISSUER ILIKE '%palantir%'` (and `TITLEOFCLASS` ~ 'COM') → pick dominant CUSIP (there may be reused/old CUSIPs; use the mode by total VALUE).
2. Join INFOTABLE (filtered to that CUSIP) with COVERPAGE on `ACCESSION_NUMBER` to get `FILINGMANAGER_NAME`.
3. Group by manager name, `SUM(VALUE)`, order desc, take top 3 names.

## Robustness Patterns (from BigCodeBench/381 & /784)
- **Validate inputs**: assert each quarter folder exists; assert fuzzy search returns ≥1 row; raise clear errors otherwise.
- **Drop NaN defensively** on CUSIP/VALUE before aggregation.
- **Deterministic tie-breaking**: when values tie, break ties by CUSIP (Q3) or manager name (Q4) ascending so results are reproducible.
- **Write CSV-then-reload sanity** (optional debugging): persist intermediate aggregates to `/tmp/` for inspection.

## Output
Write exactly:
```json
{
  "q1_answer": <AUM number, same units the skill documents (verify thousands vs dollars)>,
  "q2_answer": <int count of distinct holdings>,
  "q3_answer": ["cusip1","cusip2","cusip3","cusip4","cusip5"],
  "q4_answer": ["Manager 1","Manager 2","Manager 3"]
}
```
to `/root/answers.json`. Do not include extra keys.

## Self-check before finishing
- [ ] Q1 AUM units match the skill's documented convention (dollars vs thousands).
- [ ] Q2 uses TABLEENTRYTOTAL or COUNT(DISTINCT CUSIP), not raw INFOTABLE row count.
- [ ] Q3 list has exactly 5 CUSIP strings, sorted by positive dollar delta desc.
- [ ] Q4 list has exactly 3 manager name strings as they appear in COVERPAGE.
