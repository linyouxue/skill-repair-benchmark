---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain some insights of fund activities such as number of holdings, AUM, and change of holdings between two quarters.
---

## Overview

The helpers define the stock-selection and aggregation semantics for this skill.
Do not silently broaden their stock universe when reproducing their results.

## Invocation convention

All helper scripts live under `<this skill dir>/scripts/`. Every example below
assumes you are running from the **parent directory that contains the skill
folder** (i.e. the directory where you can `ls 13f-analyzer/`). If you prefer,
you may `cd 13f-analyzer` first and drop the `13f-analyzer/` prefix. Do NOT
run `python3 scripts/...` from `/root` — there is no `/root/scripts/`, that
will raise `FileNotFoundError`.

The data root is `/root` and each quarter lives at `/root/<quarter>/` (for
example `/root/2025-q2/INFOTABLE.tsv`, `/root/2025-q3/INFOTABLE.tsv`). All
scripts take `--quarter` and build the per-quarter path internally.

### Analyze the holding summary of a particular fund in one quarter:

```bash
python3 13f-analyzer/scripts/one_fund_analysis.py \
    --accession_number <accession number> \
    --quarter 2025-q3
```

This script will print out several basic information of a given fund in the
requested quarter, including total number of holdings, AUM, total number of
stock holdings, etc.

Interpret the printed fields precisely:

- `Total AUM` is the fund AUM across all reported holdings.
- `Total number of holdings` counts all reported holding rows.
- `Number of stock holdings` counts rows remaining after the helper's stock
  `TITLEOFCLASS` filter. When a question asks how many stocks the fund holds,
  use this field—not total holdings, `TABLEENTRYTOTAL`, or the number of unique
  CUSIPs.


### Analyze the change of holdings of a particular fund in between two quarters:

```bash
python3 13f-analyzer/scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <accession number assigned in q3> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <accession number assigned in q2>
```

This script will print out the dynamic changes of holdings from 2025-q2 to
2025-q3. Such as newly purchased stocks ranked by notional value, and newly
sold stocks ranked by notional value.

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
python3 13f-analyzer/scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script reads `/root/<quarter>/INFOTABLE.tsv` (quarter-aware) and prints
the top-k hedge funds (by `ACCESSION_NUMBER`) holding the given CUSIP in the
requested quarter, ranked by summed notional `VALUE`. Resolve the manager name
for each accession number via `fuzzy-name-search/scripts/search_fund.py
--accession_number ... --quarter <same quarter>`.
