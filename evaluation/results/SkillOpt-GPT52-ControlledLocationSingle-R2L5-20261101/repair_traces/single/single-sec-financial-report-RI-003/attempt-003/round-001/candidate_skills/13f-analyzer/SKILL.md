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
    --quarter 2025-q2 \
```

This script will print out several basic information of a given fund on 2025-q2, including total number of holdings, AUM, total number of stock holdings, etc.

Interpret the printed fields precisely:

- `Total AUM` is the fund AUM across all reported holdings.
- `Total number of holdings` counts all reported holding rows.
- `Number of stock holdings` counts rows remaining after the helper's stock
  `TITLEOFCLASS` filter. When a question asks how many stocks the fund holds,
  use this field—not total holdings, `TABLEENTRYTOTAL`, or the number of unique
  CUSIPs.


### Analyze the change of holdings of a particular fund in between two quarters:

```bash
python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <accession number assigned in q3> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <accession number assigned in q2>
```



Example workflow for Berkshire Hathaway top increased investments from Q2 to Q3:

```bash
python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <berkshire_q3_accession> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <berkshire_q2_accession>
```

From the script output, identify the section listing holdings with positive VALUE changes, sort by `DELTA_VALUE` descending if not already sorted, and extract the top 5 CUSIPs.
This script prints cross-quarter holding changes from 2025-q2 to 2025-q3, including increases, reductions, newly opened positions, and fully sold positions based on changes in reported holding VALUE by CUSIP.



For questions asking for "top increased investment" or "top buys" between quarters, compute increases strictly by dollar VALUE delta per CUSIP:

- Within each quarter, aggregate holdings by CUSIP and sum the `VALUE` field for that CUSIP.
- Compute `DELTA_VALUE = VALUE_current_quarter - VALUE_baseline_quarter`.
- Perform an outer join on CUSIP across the two quarters and fill missing VALUEs with 0 before computing deltas.
- A new position that is missing in the baseline quarter counts as an increase with `VALUE_baseline_quarter = 0` unless the task explicitly excludes new positions.
- Reduced or closed positions produce negative deltas and should not appear in "top increased investment" results.
- Filter to `DELTA_VALUE > 0`, then rank descending by `DELTA_VALUE`.
- Return the requested top-k CUSIPs together with their delta values when the task asks for the increase amount.
### Analyze which funds hold a stock to the most extent

```bash
python3 /skills/13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script will print out the top 10 hedge funds who hold a particular stock with highest notional value.
