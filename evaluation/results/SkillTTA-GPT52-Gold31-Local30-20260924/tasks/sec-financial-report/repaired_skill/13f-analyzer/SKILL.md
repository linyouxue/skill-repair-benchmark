---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain some insights of fund activities such as number of holdings, AUM, and change of holdings between two quarters.
---

## Overview

### Analyze the holding summary of a particular fund in one quarter:

```bash
python3 scripts/one_fund_analysis.py \
    --accession_number ... \
    --quarter 2025-q2 \
```

This script will print out several basic information of a given fund in a given quarter, including total number of holdings and stock holdings.

Note: the bundled `one_fund_analysis.py` prints “Total AUM” as the sum of position `VALUE` from `INFOTABLE.tsv` (i.e., total reported 13F holdings value), not the AUM field from the filing cover page. If you must report filing-level AUM/total-value from metadata, read it from `COVERPAGE.tsv` (commonly `TABLEVALUETOTAL`, sometimes other similarly-named columns in the dataset).


### Analyze the change of holdings of a particular fund in between two quarters:

```bash
python scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <accession number assigned in q3> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <accession number assigned in q2>
```

This script will print out the dynamic changes of holdings from 2025-q2 to 2025-q3. Such as newly purchased stocks ranked by notional value, and newly sold stocks ranked by notional value.


### Analyze which funds hold a stock to the most extent

```bash
python scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script is intended to print the top-K fund managers who hold a particular stock with highest notional value.

Important: the bundled `holding_analysis.py` groups by `ACCESSION_NUMBER` and does not join to `COVERPAGE.tsv` to recover manager names, and (as shipped) it may read the wrong quarter path. For tasks that require **manager names** and correct **quarter** isolation, use the following quarter-correct, name-joined one-liner instead:

```bash
python3 - << 'PY'
import pandas as pd

data_root = "/root"
quarter = "2025-q3"  # change as needed
cusip = "<CUSIP>"    # e.g. Palantir's CUSIP

a = pd.read_csv(f"{data_root}/{quarter}/INFOTABLE.tsv", sep="\t", dtype=str)
a["VALUE"] = pd.to_numeric(a["VALUE"], errors="coerce").fillna(0.0)
a["CUSIP"] = a["CUSIP"].astype(str).str.strip().str.upper()

cp = pd.read_csv(f"{data_root}/{quarter}/COVERPAGE.tsv", sep="\t", dtype=str)
cp = cp[["ACCESSION_NUMBER","FILINGMANAGER_NAME"]].drop_duplicates("ACCESSION_NUMBER")

h = a[a["CUSIP"]==cusip].groupby("ACCESSION_NUMBER", as_index=False)["VALUE"].sum()
h = h.merge(cp, on="ACCESSION_NUMBER", how="left")

h = h.sort_values("VALUE", ascending=False).head(10)
for i, r in enumerate(h.itertuples(index=False), 1):
    print(f"Rank {i}: {r.FILINGMANAGER_NAME} (ACCESSION_NUMBER={r.ACCESSION_NUMBER}) VALUE={r.VALUE:.2f}")
PY
```

For “how many stocks are held”, prefer counting **distinct CUSIPs** after normalization (strip/upper), rather than row count.
