---
name: skilltta-task-guidance
---

# Skill: 13F quarter-over-quarter hedge fund activity analysis (Q2 vs Q3)

This skill provides a reusable workflow to answer common 13F questions from two quarter folders (e.g., `/root/2025-q2`, `/root/2025-q3`). It focuses on:

- Fuzzy-searching **COVERPAGE** to locate the correct filer and obtain an `accession_number`.
- Loading **fund-level details** (AUM / total value) for a filing.
- Loading **holdings** (INFOTABLE) for a filing.
- Counting how many stocks a filer holds (with a clear counting definition).
- Quarter-over-quarter comparison of holdings (top increases by $ value).
- Cross-fund query for a given issuer (e.g., Palantir) and ranking filers by position value.

---

## 0) Assumptions & terminology

- Each quarter folder contains extracted/tabular data derived from SEC 13F filings.
- There is a **COVERPAGE**-like table (name varies) containing filer/manager names and `accession_number`.
- There is a **holdings** table (often called INFOTABLE) containing per-security positions for each `accession_number`.
- The holdings table includes at least: `accession_number`, `cusip`, `value` (often in **$ thousands**), and optionally `ssh_prn_amt` (shares).

If multiple file formats exist, prefer **parquet** (fast + typed), otherwise CSV/TSV.

---

## 1) Robust file discovery (per quarter)

Use globbing to locate key tables by fuzzy filename patterns.

**Recommended patterns**:

- Cover page / index of filers: `*cover*`, `*COVERPAGE*`, `*filer*`, `*submission*`
- Summary page: `*summary*`, `*SUMMARYPAGE*`
- Holdings / info table: `*info*`, `*INFOTABLE*`, `*hold*`, `*positions*`

Implementation sketch:

```python
from pathlib import Path
import pandas as pd

def read_table(path: Path) -> pd.DataFrame:
    # minimal, robust reader
    if path.suffix == '.parquet':
        return pd.read_parquet(path)
    if path.suffix in ('.csv',):
        return pd.read_csv(path)
    if path.suffix in ('.tsv', '.txt'):
        return pd.read_csv(path, sep='\t')
    raise ValueError(f"Unsupported file type: {path}")

def find_one(folder: str, patterns: list[str]) -> Path:
    base = Path(folder)
    cands = []
    for pat in patterns:
        cands.extend(base.rglob(pat))
    if not cands:
        raise FileNotFoundError(f"No files matched {patterns} in {folder}")
    # prefer parquet, then shortest path
    cands = sorted(cands, key=lambda p: (p.suffix != '.parquet', len(str(p))))
    return cands[0]
```

---

## 2) Fuzzy search COVERPAGE to obtain `accession_number`

### Goal
Given a search term like `"renaissance technologies"` (or `"berkshire hathaway"`), find the **best matching filer** row and extract its `accession_number`.

### Steps
1. Load COVERPAGE-like table.
2. Identify the column that contains the manager name.
   - Common candidates: `filingmanager_name`, `company_name`, `manager_name`, `filer`, `name`.
3. Perform fuzzy matching to the search term.

Implementation sketch:

```python
from rapidfuzz import process, fuzz

def get_best_accession(cover_df: pd.DataFrame, name_col: str, accession_col: str, query: str) -> str:
    choices = cover_df[name_col].astype(str).fillna('')
    match = process.extractOne(query, choices, scorer=fuzz.WRatio)
    if match is None:
        raise ValueError(f"No match for query={query}")
    best_name, score, idx = match
    acc = cover_df.loc[idx, accession_col]
    if pd.isna(acc):
        raise ValueError(f"Matched row has null accession_number: {best_name}")
    return str(acc)
```

**Validation tip**: After matching, print/log the matched name and score; if score is low, consider normalizing strings (lowercase, remove punctuation, collapse whitespace) and/or try alternative name columns.

---

## 3) Load fund details (AUM / total value)

### Goal
For a given `accession_number`, get the fund’s AUM.

### Where AUM typically is
In 13F, the most reliable numeric proxy in extracted datasets is usually the **total value of holdings** from the summary page (often named `total_value`, `tablevalue`, `totalvalue`) and often expressed in **$ thousands**.

### Recommended procedure
1. Locate and load a SUMMARYPAGE-like table if present.
2. Filter by `accession_number`.
3. Extract `total_value` field.
4. Confirm unit:
   - If column or documentation indicates “($1000)” or values look like e.g. `1234567` for a mega-fund, treat as **thousands**.
   - Convert to dollars: `aum = total_value * 1000`.

Fallback:
- If no summary page exists, compute AUM as `sum(value)` across holdings for that accession (again checking if `value` is in $ thousands).

Implementation sketch:

```python
def compute_aum(summary_df: pd.DataFrame | None,
                holdings_df: pd.DataFrame,
                accession: str,
                value_col: str = 'value') -> float:
    if summary_df is not None and 'accession_number' in summary_df.columns:
        row = summary_df.loc[summary_df['accession_number'].astype(str) == accession]
        if len(row) == 1:
            # adapt the colname as needed
            for c in ['total_value', 'totalvalue', 'tablevalue', 'total_holdings_value']:
                if c in row.columns:
                    tv = float(row.iloc[0][c])
                    # common convention: thousands
                    return tv * 1000.0

    # fallback: sum holdings
    h = holdings_df.loc[holdings_df['accession_number'].astype(str) == accession]
    total = h[value_col].fillna(0).astype(float).sum()
    return total * 1000.0  # assuming holdings value is also $ thousands
```

---

## 4) “How many stocks are held?” — counting definition (important)

### Recommended counting definition (to avoid over/under-counting)
Count **unique equity positions by CUSIP** within an accession, after excluding non-common lines if necessary.

**Canonical approach**:
- Filter holdings to the accession.
- (Optional) Keep only rows where `put_call` is null/empty and/or `investment_discretion` etc. (dataset-dependent).
- Group by `cusip` and sum values/shares.
- The number of stocks = `nunique(cusip)` after cleaning.

Implementation sketch:

```python
def count_stocks(holdings_df: pd.DataFrame, accession: str) -> int:
    h = holdings_df.loc[holdings_df['accession_number'].astype(str) == accession].copy()
    # optional: remove option legs if present
    if 'put_call' in h.columns:
        h = h[h['put_call'].isna() | (h['put_call'].astype(str).str.strip() == '')]

    # normalize cusip
    h['cusip'] = h['cusip'].astype(str).str.strip()
    h = h[h['cusip'] != '']

    return int(h['cusip'].nunique())
```

**Why this definition?** Some filings include multiple lines per issuer (e.g., different share classes, option positions, duplicated rows). Counting unique CUSIPs is the most stable “number of stocks” measure.

---

## 5) Q2 → Q3 top 5 increases for Berkshire Hathaway (by $ value increase)

### Goal
Find the top 5 CUSIPs where Berkshire’s position value increased most from Q2 to Q3.

### Steps
1. For each quarter folder:
   - Fuzzy-search COVERPAGE with `"berkshire hathaway"` to get Q2 accession and Q3 accession.
   - Load holdings and aggregate per CUSIP: `value_by_cusip = sum(value)`.
2. Align Q2 and Q3 by CUSIP and compute:
   - `delta_value = value_q3 - value_q2` (treat missing as 0).
3. Filter `delta_value > 0`.
4. Sort descending and take top 5.
5. Return those **CUSIPs**.

Implementation sketch:

```python
def agg_by_cusip(holdings_df: pd.DataFrame, accession: str, value_col='value') -> pd.DataFrame:
    h = holdings_df.loc[holdings_df['accession_number'].astype(str) == accession].copy()
    if 'put_call' in h.columns:
        h = h[h['put_call'].isna() | (h['put_call'].astype(str).str.strip() == '')]
    h['cusip'] = h['cusip'].astype(str).str.strip()
    h[value_col] = h[value_col].fillna(0).astype(float)
    return h.groupby('cusip', as_index=False)[value_col].sum()

def top_increases(q2_agg: pd.DataFrame, q3_agg: pd.DataFrame, value_col='value', k=5) -> list[str]:
    m = q3_agg.merge(q2_agg, on='cusip', how='outer', suffixes=('_q3', '_q2')).fillna(0)
    m['delta'] = m[f'{value_col}_q3'] - m[f'{value_col}_q2']
    m = m[m['delta'] > 0].sort_values('delta', ascending=False)
    return m['cusip'].head(k).tolist()
```

**Unit note**: If `value` is in $ thousands, the ranking is unaffected (monotonic), so you can rank on raw values without converting.

---

## 6) Top-3 fund managers by Palantir position value in Q3

### Goal
Across all Q3 filings, find the top 3 managers (names) holding Palantir **by position value**.

### Steps
1. Determine Palantir CUSIP:
   - Search within Q3 holdings for rows where `issuer`/`nameOfIssuer` contains “palantir” (fuzzy/substring).
   - Extract the most common associated `cusip` among those rows.
   - (Often Palantir’s CUSIP is `69608A108`, but do not hardcode unless the dataset is known to be consistent.)
2. Filter Q3 holdings to that `cusip`.
3. Aggregate position value per `accession_number` (sum values).
4. Join to Q3 coverpage to map `accession_number -> manager_name`.
5. Sort by value desc and take top 3 manager names.

Implementation sketch:

```python
def find_cusip_for_issuer(holdings_df: pd.DataFrame, issuer_col_candidates: list[str], query: str) -> str:
    issuer_col = next((c for c in issuer_col_candidates if c in holdings_df.columns), None)
    if issuer_col is None:
        raise ValueError("No issuer/name column found to identify Palantir")

    s = holdings_df[issuer_col].astype(str).str.lower()
    hits = holdings_df[s.str.contains(query.lower(), na=False)].copy()
    if hits.empty:
        raise ValueError(f"No holdings rows matched issuer query={query}")

    hits['cusip'] = hits['cusip'].astype(str).str.strip()
    # choose the most frequent cusip among matches
    return hits['cusip'].value_counts().idxmax()

def top_managers_for_cusip(holdings_df: pd.DataFrame, cover_df: pd.DataFrame,
                          cusip: str, value_col='value',
                          accession_col='accession_number', name_col='filingmanager_name', topn=3) -> list[str]:
    h = holdings_df.copy()
    h['cusip'] = h['cusip'].astype(str).str.strip()
    h = h[h['cusip'] == cusip]
    h[value_col] = h[value_col].fillna(0).astype(float)

    by_acc = h.groupby(accession_col, as_index=False)[value_col].sum()
    merged = by_acc.merge(cover_df[[accession_col, name_col]], on=accession_col, how='left')
    merged = merged.sort_values(value_col, ascending=False)
    return merged[name_col].head(topn).astype(str).tolist()
```

---

## 7) Required output: write `/root/answers.json`

The final answer must be a JSON file with schema:

```json
{
  "q1_answer": 0,
  "q2_answer": 0,
  "q3_answer": ["..."],
  "q4_answer": ["...", "...", "..."]
}
```

Write it as:

```python
import json
from pathlib import Path

answers = {
  "q1_answer": float(aum_renaissance_q3),
  "q2_answer": int(n_stocks_renaissance_q3),
  "q3_answer": list(top5_cusips_berkshire_increase),
  "q4_answer": list(top3_manager_names_palantir_q3)
}

Path('/root/answers.json').write_text(json.dumps(answers, indent=2))
```

---

## 8) Common pitfalls & checks

- **Accession mismatch**: Ensure you use the accession returned by fuzzy match for the correct quarter folder.
- **Units**: `value` is often in **$ thousands**. Convert AUM to dollars only if the question expects raw dollars; otherwise clarify in code and keep consistent.
- **Counting stocks**: use `nunique(cusip)` after filtering out option legs if present.
- **Duplicates**: aggregate by CUSIP before comparisons.
- **Name columns vary**: implement column-candidate fallbacks for `manager_name`, `accession_number`, `issuer`.
