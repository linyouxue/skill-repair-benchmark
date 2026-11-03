---
name: 13f-analyzer
description: Perform analysis on SEC 13F filings (INFOTABLE/COVERPAGE) to obtain fund-level stats (e.g., reported value/AUM proxy, number of holdings) and changes between quarters.
---

## Overview

This skill provides helper scripts to analyze the downloaded SEC 13F dataset laid out as:

- `${DATA_ROOT}/${QUARTER}/COVERPAGE.tsv`
- `${DATA_ROOT}/${QUARTER}/INFOTABLE.tsv`

Where `${QUARTER}` is a folder like `2025-q3`.

### Path / working-directory convention

You can run the scripts either:

- From the skill directory:
  ```bash
  cd skills/13f-analyzer
  python3 scripts/one_fund_analysis.py ...
  ```

- Or from the repo root (use the full path):
  ```bash
  python3 skills/13f-analyzer/scripts/one_fund_analysis.py ...
  ```

All commands below assume you are in `skills/13f-analyzer`.

## 1) Analyze one fund in one quarter

```bash
python3 scripts/one_fund_analysis.py \
  --accession_number <ACCESSION_NUMBER> \
  --quarter 2025-q3 \
  --data_root /root
```

The script prints summary statistics, including:

- **Total positions (rows)**: number of INFOTABLE line items for this filing
- **Total distinct CUSIPs**: unique CUSIPs across all line items
- **Common stock holdings (distinct CUSIPs)**: unique CUSIPs after filtering to common equity (and excluding options when possible)
- **Total reported value**: sum of `VALUE` (13F convention is typically USD *thousands*)

When a task asks “how many stocks are held”, use **Common stock holdings (distinct CUSIPs)** (not raw row count).

## 2) Compare a fund between two quarters (Top Buys / Top Sells)

```bash
python3 scripts/one_fund_analysis.py \
  --quarter 2025-q3 \
  --accession_number <Q3_ACCESSION_NUMBER> \
  --baseline_quarter 2025-q2 \
  --baseline_accession_number <Q2_ACCESSION_NUMBER> \
  --topk 10 \
  --data_root /root
```

### How “Top Buys” is computed

The comparison is performed on **CUSIP-level common equity holdings**:

1. Load each quarter’s `INFOTABLE.tsv` and filter to the given `ACCESSION_NUMBER`.
2. Filter to likely **common-equity** rows using:
   - `TITLEOFCLASS` allowlist (normalized)
   - exclude option legs when a `PUTCALL` column exists
   - keep only share positions when `SHRSORPRN == SH` exists
3. Group by `CUSIP` and **sum `VALUE`** per quarter.
4. Outer-join the two quarters on `CUSIP`.
5. Compute `ABS_CHANGE = VALUE_now - VALUE_base`.
6. Sort by `ABS_CHANGE`:
   - **Top Buys**: largest positive `ABS_CHANGE` (includes both *new positions* and *increases*)
   - **Top Sells**: most negative `ABS_CHANGE`

## 3) Find which funds hold a stock the most (Top holders)

```bash
python3 scripts/holding_analysis.py \
  --cusip <CUSIP> \
  --quarter 2025-q3 \
  --topk 10 \
  --data_root /root
```

This prints the top managers (by total `VALUE`) holding the given CUSIP in the specified quarter. When available, it enriches results with `FILINGMANAGER_NAME` from `COVERPAGE.tsv`.
