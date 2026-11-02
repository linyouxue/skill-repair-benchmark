---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain some insights of fund activities such as number of holdings, AUM, and change of holdings between two quarters.
---

## Overview

### Invocation and data path convention

The helper scripts in `scripts/` read quarter-scoped data from
`/root/<quarter>/INFOTABLE.tsv` and `/root/<quarter>/COVERPAGE.tsv`
(e.g. `/root/2025-q2/INFOTABLE.tsv`, `/root/2025-q3/INFOTABLE.tsv`).

Run the commands below either from the skill directory (`cd 13f-analyzer`)
so that the relative `scripts/...` path resolves, or from any working
directory by giving the script path explicitly, e.g.
`python3 13f-analyzer/scripts/one_fund_analysis.py ...`. Always pass
`--quarter 2025-q2` or `--quarter 2025-q3` so the correct quarter is
loaded; the scripts do not fall back to a default quarter.

### Analyze the holding summary of a particular fund in one quarter:

```bash
python3 scripts/one_fund_analysis.py \
    --accession_number ... \
    --quarter 2025-q2
```

This script will print several basic facts about the given fund in the
specified quarter:

- `Total number of holdings` -- raw INFOTABLE row count for the fund
  (may include multiple classes per issuer).
- `Total AUM` -- sum of `VALUE` across all rows for the fund.
- `Number of stock holdings` -- **count of unique CUSIPs** after
  filtering to stock title classes. This is the caliber to use when
  answering "how many stocks does fund X hold"; it deliberately
  deduplicates share classes that share the same CUSIP.
- `Total stock AUM` -- sum of `VALUE` across the stock rows.

### Analyze the change of holdings of a particular fund in between two quarters:

```bash
python3 scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <accession number assigned in q3> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <accession number assigned in q2>
```

The comparative branch computes the quarter-over-quarter change on a
CUSIP-aligned basis:

1. For each quarter, filter to stock title classes and aggregate `VALUE`
   by unique CUSIP (so each stock issuer contributes one row).
2. Outer-join the current-quarter and baseline-quarter aggregates on
   CUSIP (via the CUSIP index) so stocks held in only one quarter are
   preserved.
3. Fill missing `VALUE` and `VALUE_base` with `0`.
4. Compute `ABS_CHANGE = VALUE - VALUE_base` (current minus baseline
   notional value).
5. Rank rows with `ABS_CHANGE > 0` in descending order to produce
   **Top Buys** -- stocks that received increased dollar investment
   from baseline quarter to current quarter. Emit CUSIPs from this
   ranking when the task asks for "top stocks ranked by dollar value
   increase".
6. Rank rows with `ABS_CHANGE < 0` to produce **Top Sells** (stocks
   that received decreased dollar investment).

Note that `ABS_CHANGE` is a notional-value delta and therefore includes
price drift; it is the correct caliber for "dollar value increase"
questions phrased in terms of 13-F reported VALUE.

### Analyze which funds hold a stock to the most extent

```bash
python3 scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script loads `/root/<quarter>/INFOTABLE.tsv` and prints the top
fund managers (by accession number) holding the given CUSIP in that
quarter, ranked by summed `VALUE`. Make sure `--quarter` matches the
quarter you want to answer about; the script does not cross quarters.
To map an accession number back to a manager name, pass it to
`fuzzy-name-search/scripts/search_fund.py --accession_number ...
--quarter <same quarter>`.
