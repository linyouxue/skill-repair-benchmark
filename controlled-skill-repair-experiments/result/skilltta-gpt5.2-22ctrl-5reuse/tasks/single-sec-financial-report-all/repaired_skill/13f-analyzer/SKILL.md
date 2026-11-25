---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain insights of fund activities such as number of holdings, 13F value (AUM), and changes of holdings between two quarters.
---

## Overview

This skill analyzes **local 13F datasets by quarter folder**, e.g.

- `/root/2025-q2`
- `/root/2025-q3`

The scripts will discover the actual `INFOTABLE.*` / `COVERPAGE.*` file (tsv/csv/parquet) inside the given quarter folder.

> 13F `VALUE` is commonly reported in **$ thousands**. These scripts assume that by default and also print dollar-converted numbers.

---

## Analyze the holding summary of a particular fund in one quarter

```bash
python3 scripts/one_fund_analysis.py \
  --accession_number <ACCESSION_NUMBER> \
  --quarter 2025-q3
```

This prints basic info for the given fund in the requested quarter, including:

- total rows (all reported lines after removing options if `PUTCALL` exists)
- **distinct securities count** (distinct non-empty CUSIPs with `VALUE > 0`; this is the intended “how many stocks” definition)
- total 13F value (AUM-like total market value)
  - if COVERPAGE has a total value field (e.g., `TOTALVALUE`/`TABLEVALUE`), it will be printed
  - INFOTABLE-summed value is always printed as a fallback/validation

Optional flags:

- `--value_in_thousands` (default: true). If your dataset already stores dollars, pass `--no-value_in_thousands`.

---

## Analyze change of holdings between two quarters (Top Buys / Top Sells)

```bash
python3 scripts/one_fund_analysis.py \
  --quarter 2025-q3 \
  --accession_number <accession number assigned in q3> \
  --baseline_quarter 2025-q2 \
  --baseline_accession_number <accession number assigned in q2>
```

This compares **aggregated position value by CUSIP** between quarters:

- builds Q2 and Q3 per-CUSIP totals (outer-join so new positions are included)
- computes `delta = value_q3 - value_q2` (in dollars if `--value_in_thousands`)
- prints Top Buys (largest positive deltas) and Top Sells (most negative deltas)

---

## Analyze which fund managers hold a stock the most (by 13F value)

```bash
python3 scripts/holding_analysis.py \
  --cusip <CUSIP> \
  --quarter 2025-q3 \
  --topk 10
```

This prints top holders for the given CUSIP in the requested quarter.

- ranks by summed `VALUE` (assumed $ thousands by default)
- maps `ACCESSION_NUMBER -> manager name` using the quarter's COVERPAGE
- aggregates by **manager name** (so one manager with multiple accessions does not appear multiple times)
