---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain some insights of fund activities such as number of holdings, AUM, and change of holdings between two quarters.
---

## Overview

### Analyze the holding summary of a particular fund in one quarter

From the repo root, call the script via its package path:

```bash
python3 13f-analyzer/scripts/one_fund_analysis.py \
  --accession_number "0000000000-00-000000" \
  --quarter 2025-q2
```

This prints basic information for the given fund in the specified quarter, including:
- total line items in the filing (rows in INFOTABLE for that accession)
- total AUM (sum of VALUE)
- number of **distinct stock positions** (unique CUSIPs after common-equity filtering)
- total stock AUM

Notes:
- "How many stocks are held" should be interpreted as the number of distinct CUSIPs held (after filtering to common-equity-like TITLEOFCLASS).

### Analyze the change of holdings of a particular fund between two quarters

```bash
python3 13f-analyzer/scripts/one_fund_analysis.py \
  --quarter 2025-q3 \
  --accession_number "<accession number assigned in q3>" \
  --baseline_quarter 2025-q2 \
  --baseline_accession_number "<accession number assigned in q2>"
```

This prints changes from baseline to current quarter:
- Top Buys: positions with the largest positive dollar change (VALUE_current - VALUE_baseline)
- Top Sells: positions with the largest negative dollar change

Implementation notes (for correct interpretation):
- Changes are computed at the **CUSIP-aggregated** level (VALUE summed per CUSIP per quarter).
- Percent change is only meaningful when baseline VALUE > 0; new positions should be treated as "new" rather than a percent increase from 0.

### Analyze which funds hold a stock the most (by notional VALUE)

```bash
python3 13f-analyzer/scripts/holding_analysis.py \
  --cusip "<stock cusip>" \
  --quarter 2025-q3 \
  --topk 10
```

This prints the top-k accession numbers holding the given CUSIP in the specified quarter, ranked by total VALUE.
