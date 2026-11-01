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

Use **both** quarter-specific accession numbers (they typically differ by quarter):

```bash
python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <q3_accession_number> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <q2_accession_number>
```

This script prints changes of holdings from baseline quarter to current quarter (e.g., newly purchased/sold holdings ranked by notional value).

#### Cross-quarter metric definition (for “increased investment” / Top Buys)
When a question asks for **“top stocks received increased investment ranked by dollar value increase”**, interpret the metric as a **VALUE change** between quarters, aggregated by security identifier:

- **Group key:** CUSIP (optionally carry along `NAMEOFISSUER`/`TITLEOFCLASS` for readability, but ranking must be by CUSIP-level dollars).
- **Aggregate per quarter:** `VALUE_current = sum(VALUE)` in the current quarter; `VALUE_baseline = sum(VALUE)` in the baseline quarter.
- **Missing positions:** treat missing as 0 (i.e., if a CUSIP is absent in one quarter, its VALUE in that quarter is 0).
- **Dollar increase:** `VALUE_DELTA = VALUE_current - VALUE_baseline`.

#### New positions vs Increased positions
Separate these concepts explicitly:

- **New positions:** `VALUE_baseline = 0` and `VALUE_current > 0`.
- **Increased positions:** `VALUE_baseline > 0` and `VALUE_current > VALUE_baseline`.

Unless the question explicitly includes “new positions”, the phrase **“increased investment”** refers to **Increased positions** (existing holdings with positive `VALUE_DELTA` and non-zero baseline).

#### Ranking and what to read from output
To answer “top N by dollar value increase”, rank by:

- `VALUE_DELTA` **descending** (largest positive increase first)

Then report the **Top-5 CUSIPs** from the increased-positions list (or from the combined list if the question explicitly says to include new positions). Use the output rows/columns corresponding to CUSIP and VALUE change (current VALUE, baseline VALUE, and delta) when present.

### Analyze which funds hold a stock to the most extent

```bash
python3 /skills/13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script will print out the top 10 hedge funds who hold a particular stock with highest notional value.
