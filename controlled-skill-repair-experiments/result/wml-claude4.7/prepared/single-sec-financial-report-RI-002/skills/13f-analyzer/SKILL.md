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

This script will print out several basic information of a given fund on 2025-q2, including total number of holdings, AUM, total number of stock holdings, etc.

**Caliber for "how many stocks does fund X hold" in a single quarter.**
The answer is the number of **unique CUSIPs after the stock `TITLEOFCLASS`
filter** — i.e., the size of the grouped stock table the helper builds
internally (`stock_infotable.groupby("CUSIP")`), *not* the raw filtered
`INFOTABLE` row count. A single CUSIP can be reported across multiple
`INFOTABLE` rows (e.g., split across accounts or sub-advisers), so the printed
`Number of stock holdings` line, which reports the pre-group row count, can
over-count stocks held. For questions phrased as "how many stocks are held by
<fund>", deduplicate by CUSIP first (equivalently, read the row count of the
grouped stock table) and report that integer. Do **not** use:

- `Total number of holdings` (unfiltered `INFOTABLE` rows, includes non-stock positions),
- `Total AUM` / `Total stock AUM` (dollar values, not counts),
- the raw `Number of stock holdings` row count when it exceeds the unique-CUSIP count.

If you need the unique-CUSIP count directly, you can derive it from the
helper's own pipeline by counting distinct CUSIPs in the stock-filtered
`INFOTABLE` slice for that `ACCESSION_NUMBER` in that quarter.

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
