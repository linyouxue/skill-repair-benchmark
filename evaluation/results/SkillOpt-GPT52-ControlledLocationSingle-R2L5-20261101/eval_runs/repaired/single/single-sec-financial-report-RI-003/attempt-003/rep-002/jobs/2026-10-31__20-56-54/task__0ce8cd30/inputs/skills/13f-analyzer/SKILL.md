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


Note: accession numbers are quarter-specific filing identifiers; when analyzing a fund across quarters, always resolve the accession number separately within each quarter's dataset before running any comparison.

### Analyze the change of holdings of a particular fund in between two quarters:

Cross-quarter comparisons require two *different* filings. Do **not** reuse an accession number across quarters.

1) Find the fund's accession number for the **current** quarter (e.g., 2025-q3) by searching that quarter's filing set.
2) Separately find the fund's accession number for the **baseline** quarter (e.g., 2025-q2).
3) Run the helper with both quarter/accession pairs:

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

This script prints cross-quarter holding changes, including increases, reductions, newly opened positions, and fully sold positions, based on quarter-over-quarter changes in reported holding **dollar VALUE** by **CUSIP**.

For questions asking for "top increased investment" or "top buys" between quarters, the ranking metric and join semantics are strictly defined as follows (do not use shares, percentage change, AUM, counts of holdings, or any other metric):

- **Aggregate within each quarter by CUSIP first**: for each quarter separately, group all rows by `CUSIP` and sum the `VALUE` field to obtain `VALUE_current` and `VALUE_baseline` per CUSIP.
- **Outer-join current vs baseline by CUSIP** and treat missing values as 0: if a CUSIP only exists in one quarter, set the missing quarter's VALUE to 0.
- Compute the dollar change: `DELTA_VALUE = VALUE_current - VALUE_baseline`.
- Define **Top Buys** as the CUSIPs with the **largest positive** `DELTA_VALUE` (this includes newly opened positions where `VALUE_baseline = 0`, unless the question explicitly excludes new positions).
- Exclude reductions/sales: keep only `DELTA_VALUE > 0`.
- Rank **descending by `DELTA_VALUE`** and return the requested top-k CUSIPs (and the delta amounts if asked).

If you rely on the helper's printed tables, ensure the section used corresponds to this CUSIP-aggregated `DELTA_VALUE` definition; if the output is not already sorted, sort by `DELTA_VALUE` descending before taking the top-k.
### Analyze which funds hold a stock to the most extent

```bash
python3 /skills/13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script will print out the top 10 hedge funds who hold a particular stock with highest notional value.
