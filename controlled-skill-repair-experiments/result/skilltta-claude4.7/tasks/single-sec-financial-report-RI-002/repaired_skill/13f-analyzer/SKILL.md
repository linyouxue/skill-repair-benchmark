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

This script prints basic information of a given fund on the chosen quarter,
including AUM (sum of `VALUE`), raw INFOTABLE row counts, and the number of
distinct stock issuer positions.

#### Quantity semantics (口径) — read this before answering count questions

INFOTABLE rows are not one-row-per-stock. A single issuer position may be
split across multiple rows because of:
- different `TITLEOFCLASS` variants (e.g., "COM", "COM CL A"),
- SHRS vs PRN `SHRS/PRNAMT` type rows,
- separate voting-authority rows (sole/shared/none),
- multi-manager or sub-advisor reporting.

Therefore:
- "Number of stock holdings" / "how many stocks are held" means **distinct
  CUSIPs after applying the stock `TITLEOFCLASS` whitelist** — i.e., one row
  per issuer position. The helper prints this as
  `Number of stock holdings (distinct CUSIPs)`.
- Raw `INFOTABLE.shape[0]` (printed as `Raw INFOTABLE rows`) is for debugging
  only; do not use it to answer "how many stocks" questions.
- AUM (`Total AUM`) remains the sum of `VALUE` over the selected rows and is
  unchanged by this deduplication rule.

When the helper's output is used downstream, always take the
`distinct CUSIPs` count for issuer-position counting.

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
