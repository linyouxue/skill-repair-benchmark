---
name: skilltta-task-guidance
description: Temporary guidance for analyzing 13F hedge fund filings across Q2/Q3 2025 SEC datasets, including fuzzy name search, AUM retrieval, holdings aggregation, cross-quarter comparison, and CUSIP-based manager ranking.
---

# SkillTTA Task Guidance: 13F Hedge Fund Analysis (Q2 vs Q3 2025)

## 0. Core Principle
Do NOT trust path/script conventions blindly. The location hint explicitly warns that:
- `13f-analyzer/SKILL.md` and `fuzzy-name-search/SKILL.md` may contain **incorrect helper script paths/invocation conventions**.
- `13f-analyzer/SKILL.md` may have a **wrong quantity convention for single-quarter holdings aggregation** (likely double-counting across multiple INFOTABLE rows per issuer, or confusing shares vs value).
- `13f-analyzer/SKILL.md` may have a **wrong Top-Buys cross-quarter computation** (e.g., not aligning CUSIPs properly, not summing duplicate CUSIP rows per quarter before diffing, or ranking by shares instead of value).

Treat any existing skill scripts as *hints only*. Verify by directly inspecting the data with pandas/sqlite before trusting outputs.

## 1. Dataset Layout
Each of `/root/2025-q2` and `/root/2025-q3` contains SEC 13F quarterly data. Typical tables/files:
- `COVERPAGE` (or `coverpage.tsv`): one row per filing, columns include `ACCESSION_NUMBER`, `FILINGMANAGER_NAME`, `REPORTCALENDARORQUARTER`.
- `SUBMISSION`: filing metadata.
- `SUMMARYPAGE`: aggregated AUM (`TABLEVALUETOTAL`) and holding count (`TABLEENTRYTOTAL`).
- `INFOTABLE`: individual positions with `ACCESSION_NUMBER`, `CUSIP`, `NAMEOFISSUER`, `VALUE` (in USD, already in dollars for 2023+ filings — verify), `SSHPRNAMT` (shares).

**First action:** `ls /root/2025-q2 /root/2025-q3` and sample a few rows of each table to confirm column names, delimiter (likely TSV with `\t`), and value units.

## 2. Fuzzy Name Search Pattern
To map a fund name → `ACCESSION_NUMBER`:
1. Load `COVERPAGE` (TSV).
2. Normalize `FILINGMANAGER_NAME` (lowercase, strip punctuation).
3. Use `rapidfuzz.process.extractOne` (or `difflib.get_close_matches`) against the normalized query (e.g., `"renaissance technologies"`, `"berkshire hathaway"`).
4. Return the row with highest score; print top-5 candidates for sanity check — some managers have multiple related filings (e.g., "BERKSHIRE HATHAWAY INC" vs subsidiaries). Pick the primary one (usually the one with largest `TABLEVALUETOTAL`).

Example (self-contained — do not rely on prior skill scripts):
```python
import pandas as pd
from rapidfuzz import process, fuzc
cp = pd.read_csv('/root/2025-q3/COVERPAGE.tsv', sep='\t', dtype=str)
cp['norm'] = cp['FILINGMANAGER_NAME'].str.lower()
matches = process.extract('renaissance technologies', cp['norm'].tolist(), limit=5)
```
Adapt the file extension/separator after inspecting the folder.

## 3. AUM & Holding Count (Q1, Q2)
Given an `ACCESSION_NUMBER`:
- **AUM**: `SUMMARYPAGE.TABLEVALUETOTAL` for that accession. Verify unit — for post-2022 filings this is already in **whole dollars** (not thousands). If value seems ~1000× too small vs public reports, multiply by 1000.
- **Number of stocks held (Q2)**: Prefer `SUMMARYPAGE.TABLEENTRYTOTAL` **BUT** the question asks "how many stocks" — this typically means **distinct CUSIPs**, not total info-table rows (one issuer can have multiple rows for different share classes or put/call). Compute **both**:
  ```python
  n_rows = (infotable.ACCESSION_NUMBER == acc).sum()
  n_cusips = infotable.loc[infotable.ACCESSION_NUMBER==acc, 'CUSIP'].nunique()
  ```
  Report `n_cusips` as the primary answer (the hint flags the aggregation quantity as wrong in the existing skill — most likely it was using `n_rows` / `TABLEENTRYTOTAL`).

## 4. Cross-Quarter Top Buys (Q3)
For Berkshire Hathaway Q2 vs Q3:
1. Fuzzy-match name in **both** quarters' COVERPAGE separately → `acc_q2`, `acc_q3`.
2. Load holdings from `INFOTABLE` for each accession.
3. **Aggregate per CUSIP within each quarter** (sum `VALUE` across duplicate rows — critical fix):
   ```python
   q2 = it_q2.groupby('CUSIP', as_index=False)['VALUE'].sum().rename(columns={'VALUE':'v_q2'})
   q3 = it_q3.groupby('CUSIP', as_index=False)['VALUE'].sum().rename(columns={'VALUE':'v_q3'})
   ```
4. Outer-merge on CUSIP, fill NaN with 0.
5. `delta = v_q3 - v_q2`. Rank **descending by dollar delta** (not shares, not percent).
6. Take top 5 CUSIPs with `delta > 0`.

Ensure `VALUE` is numeric (`pd.to_numeric(..., errors='coerce')`).

## 5. Palantir Top Holders (Q4)
1. Find Palantir CUSIP: filter `INFOTABLE` where `NAMEOFISSUER` matches `PALANTIR` (case-insensitive). The common Palantir Class A CUSIP is `69608A108` — verify from the data, don't hardcode.
2. Filter Q3 `INFOTABLE` to that CUSIP.
3. Group by `ACCESSION_NUMBER`, sum `VALUE` (handle multiple rows per filer).
4. Join to `COVERPAGE` to get `FILINGMANAGER_NAME`.
5. Sort descending by value, take top 3 **manager names** (as strings, preserve original casing from COVERPAGE).

## 6. Output Schema
Write `/root/answers.json` exactly:
```json
{
  "q1_answer": <number, AUM in dollars>,
  "q2_answer": <int, distinct CUSIP count>,
  "q3_answer": ["cusip1",...,"cusip5"],
  "q4_answer": ["Manager Name 1","Manager Name 2","Manager Name 3"]
}
```

## 7. Transferable Patterns from Retrieved Examples
- **SQLite/TSV → DataFrame** (BigCodeBench/408 style): use `pd.read_csv(sep='\t')` or `sqlite3.connect` + `pd.read_sql_query` depending on actual format. Inspect first.
- **CSV round-trip & schema discipline** (BigCodeBench/784): after computing, write a well-formed JSON matching the required schema exactly — keys, types, ordering of list elements.
- **Defensive loading** (BigCodeBench/381): check file existence (`os.path.exists`), drop NaN rows before numeric aggregation, cast columns explicitly (`pd.to_numeric`), and validate column presence before use.

## 8. Verification Checklist Before Writing answers.json
- [ ] AUM magnitude plausible (Renaissance ~ $70–100B range in 2025).
- [ ] Holding count is distinct CUSIPs, not raw row count.
- [ ] Berkshire top-buy CUSIPs all have positive Q3−Q2 delta and are sorted descending.
- [ ] Palantir CUSIP confirmed by issuer name match in data.
- [ ] JSON parses (`json.loads(open('/root/answers.json').read())`).
