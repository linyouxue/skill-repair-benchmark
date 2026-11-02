---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain some insights of fund activities such as number of holdings, AUM, and change of holdings between two quarters.
---

## Overview

**Dataset layout:** by default these scripts expect the SEC 13F TSVs under `/root/<quarter>/`, e.g.
- `/root/2025-q3/COVERPAGE.tsv`
- `/root/2025-q3/INFOTABLE.tsv`

You can override the dataset root by setting `SEC_13F_DATA_ROOT`.

**Path convention:** commands below assume your working directory is the repository root.

### Analyze the holding summary of a particular fund in one quarter

```bash
python3 skills/13f-analyzer/scripts/one_fund_analysis.py \
  --accession_number <accession_number> \
  --quarter 2025-q3
```

This script prints basic information for the given filing, including:
- Total rows (positions) and total value (AUM proxy, in the file's `VALUE` units)
- Common-equity rows and **unique common-equity CUSIPs** (options excluded)

For questions like "How many stocks are held", use **unique common-equity CUSIPs** (not the raw row count).

### Analyze the change of holdings between two quarters (Top Buys / Top Sells)

```bash
python3 skills/13f-analyzer/scripts/one_fund_analysis.py \
  --quarter 2025-q3 \
  --accession_number <accession number assigned in q3> \
  --baseline_quarter 2025-q2 \
  --baseline_accession_number <accession number assigned in q2>
```

This script:
1. Loads each quarter's `INFOTABLE` for the given accession number.
2. Filters to common-equity rows (excludes options via `PUTCALL` when present).
3. Aggregates by CUSIP within each quarter.
4. Computes `ABS_CHANGE = VALUE_current - VALUE_base` per CUSIP.

**Top Buys** are CUSIPs with `ABS_CHANGE > 0`, ranked by `ABS_CHANGE` descending (new positions count as buys with a base value of 0).

### Analyze which funds hold a stock the most (top managers)

```bash
python3 skills/13f-analyzer/scripts/holding_analysis.py \
  --cusip <stock cusip> \
  --quarter 2025-q3 \
  --topk 10
```

This script prints the top-k fund managers (with names) holding the given CUSIP by total value in the specified quarter (common-equity positions; options excluded).
