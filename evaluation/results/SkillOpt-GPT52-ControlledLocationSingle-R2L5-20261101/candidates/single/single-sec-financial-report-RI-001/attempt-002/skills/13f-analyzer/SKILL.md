---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain some insights of fund activities such as number of holdings, AUM, and change of holdings between two quarters.
---

## Overview

The helpers define the stock-selection and aggregation semantics for this skill.
Do not silently broaden their stock universe when reproducing their results.



Run all helper commands from the repository root. Quarter datasets are expected under `/root/<quarter>/INFOTABLE.tsv` (for example `/root/2025-q2/INFOTABLE.tsv` and `/root/2025-q3/INFOTABLE.tsv`). Use fully qualified helper paths such as `python3 13f-analyzer/scripts/...` so the commands work without changing directories.



Do not `cd` into subdirectories when running helpers. All examples assume the current working directory is the repository root, and helpers will read quarter data from `/root/<quarter>/INFOTABLE.tsv` for the `--quarter`/`--baseline_quarter` you pass.
### Analyze the holding summary of a particular fund in one quarter:

```bash
python3 13f-analyzer/scripts/one_fund_analysis.py \
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



Accession numbers are quarter-specific: you must look up and pass the Q3 accession number for `--accession_number` and the (potentially different) Q2 accession number for `--baseline_accession_number`. The helper compares holdings loaded from `/root/2025-q3/INFOTABLE.tsv` vs `/root/2025-q2/INFOTABLE.tsv` based on those two accessions.

```bash
python3 13f-analyzer/scripts/one_fund_analysis.py \
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

1. In each quarter, select the quarter-appropriate accession number (current quarter uses `--accession_number`, baseline uses `--baseline_accession_number`) and apply the same stock `TITLEOFCLASS` filter used by the helper. Ensure the holdings are sourced from `/root/<quarter>/INFOTABLE.tsv` corresponding to each quarter.
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

This script will print out the top 10 hedge funds who hold a particular stock with highest notional value.
