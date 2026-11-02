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
    --quarter 2025-q2 \
```

This script will print basic information for a given fund in one quarter.

**Count semantics (important — choose the right count):**

The helper prints both **position counts** (unique CUSIPs) and **line-item counts** (raw rows). For questions phrased like **“how many stocks does the fund hold?”**, use the **stock position count**, not the first number you see.

- **Number of stock holdings** (**use for “how many stocks”**): the count of **unique normalized CUSIPs** among rows whose `TITLEOFCLASS` passes the helper’s equity-like filter and (when present) whose `PUTCALL` is blank/NA (options excluded).
- **Total number of holdings** (all securities): the count of **unique normalized CUSIPs** across the entire filing’s `INFOTABLE.tsv` for that accession (may include options and non-common-equity classes; blank CUSIPs are ignored).
- **… (line items)**: raw row counts before/after the stock filter. Use these only when explicitly asked for **“line items/rows”** or for debugging.

AUM values are computed by summing `VALUE` across the relevant rows (all rows for Total AUM; filtered rows for Total stock AUM). Keep units exactly as in `INFOTABLE.tsv` (do not rescale unless the dataset documentation explicitly says to).

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

```bash
python3 /skills/13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script will print out the top 10 hedge funds who hold a particular stock with highest notional value.
