---
name: skilltta-task-guidance
description: Temporary guidance for analyzing 13F hedge fund filings across Q2 and Q3 2025 using SQLite datasets in /root/2025-q2 and /root/2025-q3.
---

# 13F Cross-Quarter Analysis Guidance

## Dataset Layout
- `/root/2025-q2/` and `/root/2025-q3/` each contain SEC 13F filings, typically as SQLite databases (e.g., `form13f.db` or similar). Inspect with `ls` and `sqlite3 <file> '.tables'` first.
- Expected tables (names may vary): `COVERPAGE` (filer metadata, filingmanager_name, accession_number), `SUBMISSION` (accession headers), `INFOTABLE`/`FORM13FTABLE` (per-holding rows with `cusip`, `nameofissuer`, `value`, `sshprnamt`), `SUMMARYPAGE` (AUM / `tableValueTotal`).

## Core Query Pattern (reuse the retrieved sqlite3 + pandas pattern)
```python
import sqlite3, pandas as pd
def q(db, sql, params=()):
    with sqlite3.connect(db) as c:
        return pd.read_sql_query(sql, c, params=params)
```

## Fuzzy Matching a Fund Name -> accession_number
Use `LIKE` with wildcards on `COVERPAGE.filingmanager_name` (case-insensitive). If multiple rows match, pick the one with the largest `tableValueTotal` in SUMMARYPAGE (the real fund, not a small affiliate).
```sql
SELECT accession_number, filingmanager_name
FROM COVERPAGE
WHERE LOWER(filingmanager_name) LIKE '%renaissance technologies%';
```
Then join to SUMMARYPAGE for AUM:
```sql
SELECT tableValueTotal, tableEntryTotal FROM SUMMARYPAGE WHERE accession_number = ?;
```
- Q1 AUM: `tableValueTotal` for the chosen Renaissance accession in Q3. Note SEC 13F values are often stored in whole dollars in 2023+ filings (previously thousands); verify by sanity-checking magnitude.
- Q2 stock count: number of distinct holdings. Prefer `COUNT(DISTINCT cusip)` from INFOTABLE for the accession, OR use `tableEntryTotal` from SUMMARYPAGE. If they disagree, the distinct-CUSIP count is the "stocks held" answer.

## Q3: Cross-Quarter Top Buys (Berkshire Hathaway)  **critical fix point**
The common bug: using filingmanager_name LIKE 'BERKSHIRE%' can match multiple accessions, or joining Q2 and Q3 holdings without aligning on CUSIP (and treating sold-to-zero as a buy). Follow this exact flow:

1. In each quarter DB separately, resolve ONE accession_number for Berkshire Hathaway (prefer the filer whose SUMMARYPAGE.tableValueTotal is the largest among matches; typically filingmanager_name = 'BERKSHIRE HATHAWAY INC').
2. Pull holdings per quarter, aggregating by CUSIP (same fund can list same CUSIP across multiple rows for different share classes/managers):
```sql
SELECT cusip, SUM(value) AS value, SUM(sshprnamt) AS shares
FROM INFOTABLE WHERE accession_number = ? GROUP BY cusip;
```
3. Merge Q2 and Q3 on `cusip` with an **outer join**, filling missing sides with 0 so new positions count as full increases:
```python
m = q3.merge(q2, on='cusip', how='outer', suffixes=('_q3','_q2')).fillna(0)
m['delta_value'] = m['value_q3'] - m['value_q2']
```
4. Rank by `delta_value` descending and take top 5 CUSIPs where `delta_value > 0`. Do NOT filter out brand-new positions (q2 value = 0). Do NOT rank by share-count delta — the question asks dollar value increase.
5. Return CUSIPs as uppercase strings exactly as stored.

## Q4: Top-3 Managers Holding Palantir in Q3
1. Find Palantir CUSIP by searching INFOTABLE (Q3) for `nameofissuer LIKE '%PALANTIR%'`; take the most common CUSIP (Palantir Class A common = `69608A108`, but confirm from data).
2. Aggregate Q3 holdings of that CUSIP by accession_number, then join to COVERPAGE for `filingmanager_name`:
```sql
SELECT c.filingmanager_name, SUM(i.value) AS v
FROM INFOTABLE i JOIN COVERPAGE c USING(accession_number)
WHERE i.cusip = ? GROUP BY c.filingmanager_name ORDER BY v DESC LIMIT 3;
```
3. Return the three manager names as they appear in COVERPAGE (preserve original casing).

## Output
Write `/root/answers.json` with keys exactly: `q1_answer` (number), `q2_answer` (number), `q3_answer` (list of 5 CUSIP strings), `q4_answer` (list of 3 manager name strings). Use `json.dump` with `indent=2`.

## Robustness Tips (from retrieved patterns)
- Wrap DB access in `with sqlite3.connect(...) as conn` and use `pd.read_sql_query` (BigCodeBench/408 pattern).
- Validate file existence before opening (BigCodeBench/381 pattern): raise/log a clear error if the expected .db file is missing; discover actual filename via `os.listdir`.
- Before trusting a schema, run `PRAGMA table_info(<table>)` to confirm column names (they vary: `value` vs `value_usd`, `sshprnamt` vs `shrsOrPrnAmt`).
- Normalize text comparisons with `LOWER()` and `TRIM()`.
