---
name: skilltta-task-guidance
---

## Purpose
Provide a repeatable workflow to answer 13F-quarter comparison questions from locally downloaded SEC filing folders (e.g., `/root/2025-q2`, `/root/2025-q3`). The workflow covers:
- Fuzzy searching **COVERPAGE** to locate the best-matching manager and extract its `accession_number`.
- Loading a filing by `accession_number` to get fund AUM/total value and holdings.
- Counting distinct stocks held.
- Comparing Q2 vs Q3 holdings to rank increases by dollar value.
- Finding top managers holding a given stock (e.g., Palantir) in Q3.

> Note: Many 13F datasets store **position market value in thousands of USD** (`value` often means `$ * 1000`). Be consistent across quarters.

---

## Assumptions about local dataset layout
You typically have one of these patterns inside each quarter folder:
- A “normalized” dataset with files like `COVERPAGE.*` and `INFOTABLE.*` (csv/parquet/json) including an `accession_number` column.
- A raw EDGAR extraction with per-accession subfolders containing `primary_doc.xml`, `infotable.xml`, or `informationtable.xml`.

If you’re unsure, first enumerate files:
```bash
ls -R /root/2025-q3 | head
find /root/2025-q3 -maxdepth 3 -type f | head
```

---

## Step 1 — Fuzzy search COVERPAGE to get the accession_number
Goal: given a manager name string (e.g., `renaissance technologies`), find the best matching row in Q3 COVERPAGE and read its `accession_number`.

### Recommended implementation pattern (robust fallback)
1) Try to locate a “COVERPAGE” table file:
```bash
find /root/2025-q3 -iname '*coverpage*' -type f
```

2) Load it with pandas based on extension:
```python
import pandas as pd
from pathlib import Path

def load_table(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == '.csv':
        return pd.read_csv(p)
    if p.suffix.lower() in ('.parquet', '.pq'):
        return pd.read_parquet(p)
    if p.suffix.lower() in ('.json',):
        return pd.read_json(p, lines=True)
    raise ValueError(f"Unsupported table format: {p}")
```

3) Fuzzy match by manager name column. Common column names:
- `filing_manager_name`, `manager_name`, `company_name`, `filer_name`, `name`

Use rapidfuzz:
```python
from rapidfuzz import process, fuzz

def best_accession_from_coverpage(cover_df: pd.DataFrame, query: str) -> str:
    # choose candidate name column
    for col in [
        'filing_manager_name','manager_name','company_name','filer_name','name'
    ]:
        if col in cover_df.columns:
            name_col = col
            break
    else:
        raise KeyError(f"No known name column in COVERPAGE. Columns={list(cover_df.columns)}")

    if 'accession_number' not in cover_df.columns:
        raise KeyError("COVERPAGE missing accession_number")

    names = cover_df[name_col].fillna('').astype(str).tolist()
    match, score, idx = process.extractOne(query, names, scorer=fuzz.WRatio)
    row = cover_df.iloc[idx]
    return str(row['accession_number'])
```

### If your repository provides a helper script (fuzzy-name-search)
If you have an existing `fuzzy-name-search` tool, prefer it—**but ensure paths are absolute and consistent**:
- Pass the quarter root (e.g., `/root/2025-q3`) explicitly.
- Pass the intended table name explicitly (`COVERPAGE`).

If the helper script assumes relative paths (common source of failure), patch/call it with absolute paths.

---

## Step 2 — Load fund details by accession_number (AUM + holdings)
Once you have `accession_number`, you need:
- **AUM / total value** for Q3 (from coverpage “summary” fields)
- **Holdings table** (infotable) to count stocks and compare

### AUM / Total Value
In many 13F cover pages, AUM-like metric is `total_value` / `totalValue` / `table_value_total`.
Pattern:
```python
def get_total_value_from_coverpage_row(row) -> float:
    # Return numeric total value; interpret units according to dataset
    for col in ['total_value','totalValue','table_value_total','total_holdings_value','value_total']:
        if col in row.index:
            v = row[col]
            if pd.isna(v):
                continue
            return float(v)
    raise KeyError("No total value field found in coverpage row")
```

If total value is in `$ thousands`, the AUM in dollars is `total_value * 1000`.

### Holdings (INFOTABLE)
Locate the infotable table and filter by accession:
```python

def load_infotable(quarter_root: str) -> pd.DataFrame:
    import glob
    import os
    pats = [
        '*infotable*.csv','*informationtable*.csv',
        '*infotable*.parquet','*informationtable*.parquet',
        '*infotable*.json','*informationtable*.json'
    ]
    files = []
    for pat in pats:
        files += glob.glob(os.path.join(quarter_root, '**', pat), recursive=True)
    if not files:
        raise FileNotFoundError("Could not find INFOTABLE in quarter folder")
    # pick the most plausible (largest) file
    path = max(files, key=lambda p: os.path.getsize(p))
    return load_table(path)


def holdings_for_accession(infotable_df: pd.DataFrame, accession: str) -> pd.DataFrame:
    if 'accession_number' not in infotable_df.columns:
        raise KeyError("INFOTABLE missing accession_number")
    h = infotable_df[infotable_df['accession_number'].astype(str) == str(accession)].copy()
    if h.empty:
        raise ValueError(f"No holdings found for accession {accession}")
    return h
```

Common holdings columns:
- `cusip`
- `value` (often $ thousands)
- `sshprnamt` / `shares`
- `nameofissuer` / `issuer`

---

## Step 3 — Q1/Q2 style questions
### Q1: AUM of Renaissance Technologies in Q3
Procedure:
1) `cover_q3 = load_table(COVERPAGE in /root/2025-q3)`
2) `acc = best_accession_from_coverpage(cover_q3, "renaissance technologies")`
3) Select that row and read total value/AUM with `get_total_value_from_coverpage_row`.

### Q2: How many stocks are held by Renaissance in Q3
Procedure:
1) Load INFOTABLE for Q3
2) Filter holdings by `accession_number == acc`
3) Count distinct CUSIPs (or distinct issuers). Prefer CUSIP for “stocks held”:
```python
num_stocks = holdings['cusip'].astype(str).nunique()
```

---

## Step 4 — Q2 vs Q3 comparison for Berkshire Hathaway (top increases)
Goal: top 5 stocks with **largest dollar value increase** from Q2 to Q3.

Procedure:
1) Find `acc_q2` by fuzzy searching Q2 COVERPAGE for "berkshire hathaway".
2) Find `acc_q3` by fuzzy searching Q3 COVERPAGE for "berkshire hathaway".
3) Load Q2 and Q3 holdings for each accession.
4) Aggregate holdings by CUSIP (some filings can have duplicates):
```python
q2g = q2_hold.groupby('cusip', as_index=False)['value'].sum()
q3g = q3_hold.groupby('cusip', as_index=False)['value'].sum()
```
5) Outer-join and compute increase:
```python
m = q3g.merge(q2g, on='cusip', how='outer', suffixes=('_q3','_q2')).fillna(0)
m['increase'] = m['value_q3'] - m['value_q2']
```
6) Filter to increases only (`increase > 0`) and sort desc; take top 5 cusips:
```python
top5 = m[m['increase']>0].sort_values('increase', ascending=False).head(5)['cusip'].tolist()
```

Unit note: if `value` is in $ thousands, increase is also $ thousands; ranking is invariant.

---

## Step 5 — Top-3 fund managers holding Palantir in Q3 by share value
Goal: identify Palantir CUSIP, then rank Q3 managers by their position value in that CUSIP.

### 5.1 Find Palantir CUSIP
Options (in priority order):
1) Search Q3 INFOTABLE for issuer name contains `palantir` and read most common CUSIP:
```python
pal = infotable_q3[infotable_q3['nameofissuer'].str.contains('palantir', case=False, na=False)]
# choose dominant cusip
pal_cusip = pal['cusip'].value_counts().idxmax()
```
2) If your environment includes a CUSIP mapping tool, use it, but the infotable-search is usually enough.

### 5.2 Rank managers by position value
1) Filter Q3 holdings to `cusip == pal_cusip`.
2) Sum value per `accession_number`:
```python
pal_pos = infotable_q3[infotable_q3['cusip'].astype(str) == str(pal_cusip)].copy()
by_acc = pal_pos.groupby('accession_number', as_index=False)['value'].sum()
```
3) Map accession_number to manager name using Q3 COVERPAGE:
```python
# determine coverpage name column similarly to earlier
name_col = ...
acc_to_name = cover_q3.set_index('accession_number')[name_col].to_dict()
by_acc['manager'] = by_acc['accession_number'].map(acc_to_name)
```
4) Sort by `value` desc and take top 3 distinct managers:
```python
top3_mgrs = by_acc.sort_values('value', ascending=False)['manager'].dropna().head(3).tolist()
```

---

## Step 6 — Write `/root/answers.json`
Create exactly the requested schema:
```python
import json
from pathlib import Path

answers = {
  "q1_answer": float(q1_aum),
  "q2_answer": int(q2_num_stocks),
  "q3_answer": list(top5_cusips),
  "q4_answer": list(top3_mgrs)
}

Path('/root/answers.json').write_text(json.dumps(answers, indent=2))
```

---

## Common pitfalls & checks
- **Wrong quarter folder**: Always pass `/root/2025-q2` vs `/root/2025-q3` explicitly.
- **Accession mismatch**: Accession numbers change by quarter; re-run fuzzy search in each quarter.
- **Multiple name variants**: For Berkshire, query variants like `"BERKSHIRE HATHAWAY INC"` if needed.
- **Value units**: Verify if `value` is in thousands. If converting to dollars for “AUM”, multiply by 1000 only if confirmed by dataset docs.
- **CUSIP formatting**: Keep as string; preserve leading zeros.

---

## Minimal end-to-end pseudo-flow
1) Q3 Renaissance accession via COVERPAGE fuzzy match → AUM from coverpage row.
2) Q3 Renaissance holdings via INFOTABLE filtered by accession → distinct `cusip` count.
3) Q2 & Q3 Berkshire accessions via COVERPAGE fuzzy match → holdings diff by cusip/value → top5 increases.
4) Palantir cusip via INFOTABLE issuer search → group by accession → map to manager names via COVERPAGE → top3.
