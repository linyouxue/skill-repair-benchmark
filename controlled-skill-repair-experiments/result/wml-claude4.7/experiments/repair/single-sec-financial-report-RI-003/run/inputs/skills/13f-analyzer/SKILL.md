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

This script compares holdings from the baseline quarter to the current quarter.
It aggregates the fund's reported rows per `CUSIP` in each quarter (summing
`VALUE` and `SSHPRNAMT`) and performs an outer merge on `CUSIP`, so brand-new
positions and fully-exited positions are preserved with zero on the missing
side. From the merged frame it derives both a share-count delta
(`SHARE_CHANGE = SSHPRNAMT - SSHPRNAMT_base`) and a dollar-value delta
(`ABS_CHANGE = VALUE - VALUE_base`).

Identifying stocks that "received increased investment" (true top buys):

- A position only counts as "increased investment" when the fund actually
  added shares, i.e. `SHARE_CHANGE > 0`. A positive `VALUE` delta alone is
  not sufficient: an unchanged share count combined with a price rise will
  also produce a positive `VALUE` delta, so ranking on `ABS_CHANGE` without
  first filtering on `SHARE_CHANGE` conflates price appreciation with new
  purchases.
- To rank the top buys, take the subset of positions with `SHARE_CHANGE > 0`
  and order them by `ABS_CHANGE` descending; report their `CUSIP`s. The
  helper prints this ordered list under the heading
  "Top Increased Investments (share count up), ranked by dollar-value
  increase". Use this list — not the raw value-delta diagnostic — for
  questions phrased as "stocks that received increased investment",
  "top buys", or "stocks the manager added to".
- The symmetric "Top Decreased Investments" list (`SHARE_CHANGE < 0`,
  ordered by most-negative `ABS_CHANGE`) identifies positions the fund
  actually trimmed or exited.
- The helper also prints a plain value-delta diagnostic view
  ("Top Positions by VALUE delta"). Treat it as a notional check only and
  reconcile it against the share-count-filtered ranking before reporting any
  "increased investment" answer.

### Analyze which funds hold a stock to the most extent

```bash
python3 /skills/13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script will print out the top 10 hedge funds who hold a particular stock with highest notional value.
