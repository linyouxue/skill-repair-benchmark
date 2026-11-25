---
name: skilltta-task-guidance
---

# SkillTTA Task Guidance — 13F Q2/Q3 2025 Hedge Fund Activity

This skill provides a **robust, reusable workflow** to answer the 4 questions using the local datasets in:

- `/root/2025-q2`
- `/root/2025-q3`

It emphasizes **correct file-path conventions**, **consistent units**, and **correct aggregation logic** for:

- single-quarter AUM and holdings count
- cross-quarter “Top Buys” (value increases)
- manager ranking by a specific security (Palantir)

---

## 0) Data assumptions & file discovery (path conventions)

Do **not** hardcode auxiliary script paths. Instead:

1. Treat the quarter folder as the base input.
2. Discover the actual files inside using `glob`.

Recommended discovery helper:

```python
from pathlib import Path

def find_one(base_dir: str, candidates: list[str]) -> Path:
    base = Path(base_dir)
    for name in candidates:
        hits = list(base.rglob(name))
        if hits:
            return hits[0]
    raise FileNotFoundError(f"None of {candidates} found under {base_dir}")
```

Typical candidate names (adapt if your dataset uses different naming):

- Cover page / submission metadata:
  - `COVERPAGE.tsv`, `COVERPAGE.csv`, `coverpage.parquet`
  - sometimes `SUBMISSION.tsv` contains manager + accession mappings
- Holdings table:
  - `INFOTABLE.tsv`, `INFOTABLE.csv`, `infotable.parquet`

Reading helper (auto by suffix):

```python
import pandas as pd

def read_table(path):
    path = str(path)
    if path.endswith(".parquet"):
        return pd.read_parquet(path)
    if path.endswith(".tsv"):
        return pd.read_csv(path, sep="\t", dtype=str)
    return pd.read_csv(path, dtype=str)
```

> Always load as `dtype=str` first; then convert numeric columns safely.

---

## 1) Fuzzy search COVERPAGE to get `accession_number`

For manager identification (e.g., *Renaissance Technologies*, *Berkshire Hathaway*), the correct process is:

1. Load COVERPAGE for the quarter
2. Fuzzy match the manager name against the manager-name column
3. Select the best row → get `accession_number`

### 1.1 Identify the manager name column

Common manager columns:
- `filingmanager_name`
- `manager_name`
- `nameofinstitution`

Choose the first existing from a preference list:

```python
POSSIBLE_NAME_COLS = [
  "filingmanager_name", "manager_name", "nameofinstitution",
  "filing_manager_name", "company_name"
]
```

### 1.2 Fuzzy matching

Use `rapidfuzz` if available; otherwise fallback to `difflib`.

```python
from rapidfuzz import process, fuzz

def fuzzy_best_match(df, name_col, query):
    choices = df[name_col].fillna("").astype(str).tolist()
    best = process.extractOne(query, choices, scorer=fuzz.WRatio)
    # best = (matched_string, score, index)
    return best
```

Then pick that row’s `accession_number` (or similar key). Common accession columns:
- `accession_number`
- `accessionnumber`

Validate the hit by checking the score (e.g., `>= 85`) and optionally printing the matched name.

---

## 2) Obtain fund details & compute AUM (Q1)

**Question 1:** “In Q3, what's the AUM of Renaissance Technologies founded by Jim Simons?”

### 2.1 Prefer COVERPAGE “total value” if present

Some datasets include a coverpage field representing total 13F value, commonly in **$ thousands**.
Look for columns like:
- `total_value`
- `tablevalue`
- `totalvalue`
- `totalsecvalue`

If found, parse numeric and convert units:

- If documented as **$ thousands**, do: `aum_dollars = total_value * 1000`.

### 2.2 Otherwise compute AUM from holdings (INFOTABLE)

If COVERPAGE lacks total value, compute:

- Filter INFOTABLE to the fund’s `accession_number`
- Sum `value` column (typically **$ thousands**) and multiply by 1000

Robust numeric parse:

```python
import pandas as pd

def to_num(s):
    return pd.to_numeric(
        pd.Series(s).astype(str).str.replace(",", "", regex=False),
        errors="coerce"
    )
```

**AUM definition for this task:**
- Use **total market value of 13F holdings** (not firm-wide AUM).
- Output as a single **number in dollars**.

---

## 3) Count how many stocks are held (Q2)

**Question 2:** “How many stocks are held by Renaissance?”

For a **single quarter**, the correct “number of stocks held” should be:

- Count of **distinct CUSIPs** in the fund’s INFOTABLE for that accession.

Rules (recommended and consistent):

1. Filter to the fund’s `accession_number`.
2. Use `cusip` as the instrument identifier.
3. Count **unique** CUSIPs where position is meaningful:
   - `value > 0` OR `sshprnamt > 0`
4. If the same CUSIP appears multiple times (rare but possible), count it once.
5. Ignore put/call flags unless the dataset has both equity and option lines; if both exist, still count distinct CUSIP once.

Example:

```python
hold = infotable[infotable["accession_number"] == acc]
hold["value_num"] = to_num(hold["value"])  # usually $ thousands
n_stocks = hold.loc[hold["value_num"].fillna(0) > 0, "cusip"].nunique()
```

---

## 4) Cross-quarter Top Buys by Berkshire (Q3)

**Question 3:** “From Q2 to Q3, top 5 stocks received increased investment by Berkshire Hathaway, ranked by dollar value increase. Answer stock CUSIPs.”

### 4.1 Get accession numbers for each quarter

- Fuzzy search Q2 COVERPAGE for “berkshire hathaway” → `acc_q2`
- Fuzzy search Q3 COVERPAGE for “berkshire hathaway” → `acc_q3`

### 4.2 Build per-quarter position value by CUSIP

For each quarter:

1. Filter INFOTABLE to `accession_number`
2. Convert `value` to numeric
3. Aggregate by CUSIP using **sum** (safe if duplicates exist)
4. Convert to dollars if `value` is in $ thousands

```python

def positions_by_cusip(infotable, acc):
    h = infotable[infotable["accession_number"] == acc].copy()
    h["value_num"] = to_num(h["value"]).fillna(0)
    # assume value is in $ thousands
    pos = h.groupby("cusip", as_index=False)["value_num"].sum()
    pos["value_dollars"] = pos["value_num"] * 1000
    return pos[["cusip", "value_dollars"]]
```

### 4.3 Compute increases (Top Buys)

Correct Top Buys logic:

- Outer-merge Q2 and Q3 by CUSIP
- Fill missing with 0
- Compute `delta = value_q3 - value_q2`
- Keep `delta > 0`
- Sort by `delta desc`
- Take top 5 CUSIPs

```python
p2 = positions_by_cusip(info_q2, acc_q2).rename(columns={"value_dollars":"v2"})
p3 = positions_by_cusip(info_q3, acc_q3).rename(columns={"value_dollars":"v3"})

m = p2.merge(p3, on="cusip", how="outer")
m[["v2","v3"]] = m[["v2","v3"]].fillna(0)
m["delta"] = m["v3"] - m["v2"]

top5 = (
  m[m["delta"] > 0]
  .sort_values("delta", ascending=False)
  .head(5)["cusip"].tolist()
)
```

Pitfalls to avoid:
- Do **not** rank by share-count changes; use **dollar value** change.
- Do **not** inner-join (it drops new positions).

---

## 5) Top-3 fund managers holding Palantir by share value (Q4)

**Question 4:** “List top-3 fund managers (name) which have invested Palantir in terms of share value in Q3.”

### 5.1 Get Palantir CUSIP

Preferred method:

- Search Q3 INFOTABLE for issuer name containing “PALANTIR” (case-insensitive)
- Extract the dominant/most frequent `cusip` from those matches

```python
cand = info_q3[info_q3["nameofissuer"].str.contains("palantir", case=False, na=False)]
palantir_cusip = cand["cusip"].value_counts().index[0]
```

(If you already know it, Palantir is commonly `69608A108`, but still verify from the dataset.)

### 5.2 Compute manager ranking

Steps:

1. Filter Q3 INFOTABLE to `cusip == palantir_cusip`
2. For each `accession_number`, sum `value` (again typically $ thousands)
3. Map `accession_number -> manager name` using Q3 COVERPAGE
4. Aggregate by manager name (in case multiple accessions exist)
5. Sort desc, take top 3

```python
pal = info_q3[info_q3["cusip"] == palantir_cusip].copy()
pal["value_num"] = to_num(pal["value"]).fillna(0)
pal_val = pal.groupby("accession_number", as_index=False)["value_num"].sum()
pal_val["value_dollars"] = pal_val["value_num"] * 1000

# accession -> manager name mapping
acc2name = cover_q3.set_index("accession_number")[name_col].to_dict()
pal_val["manager"] = pal_val["accession_number"].map(acc2name)

top3 = (
  pal_val.groupby("manager", as_index=False)["value_dollars"].sum()
  .sort_values("value_dollars", ascending=False)
  .head(3)["manager"].tolist()
)
```

---

## 6) Write `answers.json` to `/root/answers.json`

Required schema:

```json
{
  "q1_answer": 0,
  "q2_answer": 0,
  "q3_answer": ["..."],
  "q4_answer": ["...", "...", "..."]
}
```

Write with:

```python
import json
from pathlib import Path

answers = {
  "q1_answer": float(aum_dollars),
  "q2_answer": int(n_stocks),
  "q3_answer": top5,
  "q4_answer": top3,
}

Path("/root/answers.json").write_text(json.dumps(answers, indent=2))
```

---

## 7) Quick validation checklist

- Q1 AUM is for **Q3 Renaissance** and is **in dollars** (not thousands).
- Q2 holdings count is **distinct CUSIPs** for that accession in Q3.
- Q3 Top Buys uses **value increase** (`v3 - v2`) and returns **CUSIPs**.
- Q4 Top managers are **manager names** (from COVERPAGE) ranked by **Palantir position value** in Q3.
