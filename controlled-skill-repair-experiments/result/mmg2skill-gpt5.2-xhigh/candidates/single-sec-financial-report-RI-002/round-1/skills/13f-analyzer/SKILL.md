---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain some insights of fund activities such as number of holdings, AUM, and change of holdings between two quarters.
---

## Overview

The helper programs are installed under `/skills/13f-analyzer/scripts`. Run them
from that absolute path; the task workspace is normally `/root`, so
`scripts/...` and `/root/scripts/...` are not equivalent paths. If a helper
cannot be found, check `/skills/13f-analyzer/scripts` before writing a replacement
analysis pipeline.

The helpers define the stock-selection and aggregation semantics for this skill.
Do not silently broaden their stock universe when reproducing their results.

### Analyze the holding summary of a particular fund in one quarter:

```bash
python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
    --accession_number ... \
    --quarter 2025-q2
```

Use this helper to read the fund’s quarter data and report totals such as AUM
(sum of `VALUE` for that accession number in that quarter).

For questions asking “how many stocks” the fund holds in a quarter, use the
count of distinct stock positions (unique `CUSIP`s) after the helper’s stock
filter and `CUSIP` grouping (i.e., count rows of the grouped stock table), e.g.:

```bash
python3 - <<'PY'
import sys
sys.path.append("/skills/13f-analyzer/scripts")
import one_fund_analysis as ofa

quarter = "2025-q2"
accession = "ACCESSION_NUMBER_HERE"

stock = ofa.read_one_quarter_data(accession, quarter)  # grouped by CUSIP
print(stock.shape[0])
PY
```

### Analyze the change of holdings of a particular fund in between two quarters:

```bash
python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <accession number assigned in q3> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <accession number assigned in q2>
```

This script will print out the dynamic changes of holdings from 2025-q2 to 2025-q3. Such as newly purchased stocks ranked by notional value, and newly sold stocks ranked by notional value.

For a request ranked by dollar-value increase, take the requested number of
CUSIPs from the beginning of the helper's `Top Buys` output, preserving order.
Do not rank by share-count change, percentage change, or an unfiltered
`INFOTABLE`.

If the comparison must be reproduced in custom code, preserve the helper's
pipeline exactly:

1. In each quarter, select the requested accession number and apply the same
   stock `TITLEOFCLASS` filter used by the helper.
2. Group each filtered quarter by `CUSIP` and sum `VALUE`.
3. Outer-join the two quarters and fill missing current/baseline values with 0.
4. Compute `ABS_CHANGE = current VALUE - baseline VALUE`.
5. Keep positive changes and sort `ABS_CHANGE` descending.

Before returning an answer, verify that the requested top-k contains exactly k
unique CUSIP strings in the printed order.

### Analyze which funds hold a stock to the most extent

Compute top holders from the quarter-scoped data, then map accession numbers to
fund manager names via the same quarter’s `COVERPAGE.tsv`:

```bash
python3 - <<'PY'
import pandas as pd

quarter = "2025-q3"
cusip = "CUSIP_HERE".upper()
topk = 10

it = pd.read_csv(f"/root/{quarter}/INFOTABLE.tsv", sep="\t", dtype=str)
it["CUSIP"] = it["CUSIP"].str.upper()
it["VALUE"] = it["VALUE"].astype(float)

top = (
    it[it["CUSIP"] == cusip]
      .groupby("ACCESSION_NUMBER")["VALUE"].sum()
      .sort_values(ascending=False)
      .head(topk)
      .reset_index(name="TOTAL_VALUE")
)

cp = pd.read_csv(f"/root/{quarter}/COVERPAGE.tsv", sep="\t", dtype=str)[
    ["ACCESSION_NUMBER", "FILINGMANAGER_NAME", "ISAMENDMENT"]
]
cp = cp[cp["ISAMENDMENT"] == "N"].drop_duplicates("ACCESSION_NUMBER")

out = top.merge(cp, on="ACCESSION_NUMBER", how="left")
print(out.to_string(index=False))
PY
```

This prints the top holders (by summed `VALUE`) and their `FILINGMANAGER_NAME`.
