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

#### Picking the right accession_number for each quarter

Accession numbers are per-filing, so the same manager will have **different**
accession numbers in Q2 and Q3. Resolve each quarter independently:

1. Use `/skills/fuzzy-name-search/scripts/search_fund.py --keywords "<name>" --quarter <2025-qN>` to list candidate filers. Large managers (e.g., Berkshire Hathaway) often return multiple affiliated entities.
2. Among non-amendment matches, choose the filer whose `Total AUM` (equivalently SUMMARYPAGE `tableValueTotal`) is the largest — that is the primary filer. You can confirm by running the single-quarter mode above and inspecting the printed `Total AUM`.
3. Repeat the resolution in the other quarter before invoking the cross-quarter command. Do NOT reuse a Q2 accession number in Q3.

#### What the cross-quarter output actually contains

Internally the script joins the two quarters on `CUSIP` (outer join; missing
side filled with 0) and computes a signed dollar-value delta
`ABS_CHANGE = VALUE (current quarter) - VALUE_base (baseline quarter)`.
It then prints two blocks:

- `Top 10 Buys from <baseline_quarter> to <quarter>`: rows with `ABS_CHANGE > 0`,
  sorted by `ABS_CHANGE` descending. **This block already includes both brand-new
  positions (baseline VALUE = 0) AND increases on positions that already existed
  in the baseline quarter.** Do not post-filter to "only new positions".
- `Top 10 Sells from <baseline_quarter> to <quarter>`: rows with `ABS_CHANGE < 0`,
  sorted by `ABS_CHANGE` ascending (largest dollar decrease first).

Ranking is by the printed `Abs change` column (the signed dollar-value delta),
NOT by the current-quarter notional `VALUE`. For a question of the form
"top N stocks that received increased investment, ranked by dollar value
increase", the answer is the first N rows of the Top Buys block; report their
CUSIPs as printed (upper-case, as stored).

Scope note: the cross-quarter comparison reuses the same stock `TITLEOFCLASS`
whitelist as the single-quarter mode, so the Top Buys / Top Sells blocks are
already restricted to stock holdings and are appropriate for stock-only
questions without further filtering.

### Analyze which funds hold a stock to the most extent

```bash
python3 /skills/13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script will print out the top 10 hedge funds who hold a particular stock with highest notional value.
