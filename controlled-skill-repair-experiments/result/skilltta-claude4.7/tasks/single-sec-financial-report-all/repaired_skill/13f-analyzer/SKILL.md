---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain some insights of fund activities such as number of holdings, AUM, and change of holdings between two quarters.
---

## Overview

All helper scripts live under `13f-analyzer/scripts/`. Invoke them with the
skill-folder-prefixed path (examples below assume the working directory is
`/root` or any directory that contains the `13f-analyzer/` skill folder).

## Quantity conventions (IMPORTANT)

- **AUM (dollars)**: sum of `INFOTABLE.VALUE` across every row for the
  accession, OR equivalently `SUMMARYPAGE.TABLEVALUETOTAL` for the accession.
  The scripts here use the INFOTABLE sum and report it as `Total AUM`.
- **Number of stocks held**: the number of **distinct CUSIPs** on the
  common-equity subset (after filtering `TITLEOFCLASS` to common/ADR/etc.),
  NOT the raw INFOTABLE row count. Options and multiple share classes for the
  same issuer can inflate the row count; always deduplicate on `CUSIP`.
- **Top Buys / Top Sells across quarters**: compute per-CUSIP VALUE sums
  within each quarter FIRST, then outer-merge on CUSIP, then take the dollar
  delta `v_current - v_baseline`, rank descending by that delta.

### Analyze the holding summary of a particular fund in one quarter:

```bash
python3 13f-analyzer/scripts/one_fund_analysis.py \
    --accession_number ... \
    --quarter 2025-q2
```

This prints, for the given accession in the given quarter:
- `Total number of INFOTABLE rows` (raw row count — diagnostic only)
- `Total AUM` (sum of `VALUE` across all rows for the accession, in dollars)
- `Number of stock holdings (distinct CUSIPs)` — this is the canonical
  "how many stocks are held" answer
- `Total stock AUM` (sum of `VALUE` restricted to the common-equity subset)

### Analyze the change of holdings of a particular fund between two quarters:

```bash
python3 13f-analyzer/scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <accession number assigned in q3> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <accession number assigned in q2>
```

Recipe used internally (and recommended if you redo it by hand):
1. For each quarter, filter `INFOTABLE` to the accession.
2. Restrict to common-equity rows via the `TITLEOFCLASS` whitelist.
3. `groupby('CUSIP').VALUE.sum()` per quarter so duplicate CUSIP rows are
   collapsed.
4. Outer-merge the two per-CUSIP tables on `CUSIP`, fill missing values with
   0.
5. `ABS_CHANGE = VALUE_current - VALUE_baseline`.
6. Sort descending by `ABS_CHANGE` → positive deltas are Top Buys; negative
   deltas (ascending) are Top Sells. Rank by **dollar delta**, not shares and
   not percentage.

### Analyze which funds hold a stock to the most extent

```bash
python3 13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

The script reads `INFOTABLE` and `COVERPAGE` for the requested quarter,
sums `VALUE` per `ACCESSION_NUMBER` for the given CUSIP, joins to
`COVERPAGE.FILINGMANAGER_NAME`, and prints the top-k rows as
`rank, FILINGMANAGER_NAME, ACCESSION_NUMBER, TOTAL_VALUE`. Use the printed
`FILINGMANAGER_NAME` directly for questions that ask for fund-manager names.
