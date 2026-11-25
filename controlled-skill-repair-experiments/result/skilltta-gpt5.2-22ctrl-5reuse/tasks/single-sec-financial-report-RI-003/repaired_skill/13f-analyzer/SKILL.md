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

### Analyze the holding summary of a particular fund in one quarter:

```bash
python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
    --accession_number ... \
    --quarter 2025-q2
```

This script prints basic information of a given fund in a given quarter,
including total number of holdings, AUM (sum of VALUE), and stock-only summary.

Interpret the printed fields precisely:

- `Total AUM` is the fund AUM across all reported holdings in the INFOTABLE.
  Note: `VALUE` is commonly reported in $000 in 13F datasets; the script reports
  the raw sum of `VALUE` as stored.
- `Total number of holdings` counts all reported holding rows for that filer.
- `Number of unique CUSIPs (all holdings)` counts distinct CUSIPs across all
  rows for that filer.
- `Number of stock holdings` counts holding **rows** remaining after the
  helper's stock `TITLEOFCLASS` filter.
- `Number of unique stock CUSIPs` counts distinct stock CUSIPs after the same
  filter.

When a question asks how many **stocks** a fund holds, prefer `Number of unique
stock CUSIPs` (it is robust to duplicate lines).


### Analyze the change of holdings of a particular fund between two quarters:

```bash
python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <accession number assigned in q3> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <accession number assigned in q2>
```

This script prints the dynamic changes of holdings from baseline quarter to
target quarter.

Cross-quarter Top Buys/Sells are computed as follows:

- Filter to "stock" rows using the helper's `TITLEOFCLASS` allowlist.
- Aggregate within each quarter by `CUSIP` (sum of `VALUE`).
- Outer-join Q2 vs Q3 on `CUSIP`.
- Compute `ABS_CHANGE = VALUE_q3 - VALUE_q2`.
- Rank Top Buys by descending `ABS_CHANGE` (positive deltas) and Top Sells by
  ascending `ABS_CHANGE` (most negative deltas).

Notes:
- The ranking is by **delta value**, not by Q3 notional value.
- Units follow the dataset's `VALUE` field (often $000). If you need USD,
  multiply by 1,000 when appropriate.


### Analyze which funds hold a stock to the most extent

```bash
python3 /skills/13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script prints the top-k fund managers who hold a particular stock CUSIP
with highest total notional value in the specified quarter.

By default it includes all rows for the CUSIP; if you need equity-only results
and your dataset contains a Put/Call column, add:

```bash
python3 /skills/13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10 \
    --equity_only
```
