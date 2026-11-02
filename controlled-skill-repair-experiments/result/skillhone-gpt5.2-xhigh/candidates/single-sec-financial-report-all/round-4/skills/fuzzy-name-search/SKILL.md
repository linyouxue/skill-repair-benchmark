---
name: fuzzy-name-search
description: Search capability in SEC 13F datasets, including fuzzy search a fund by (possibly inaccurate) name and searching a stock CUSIP by issuer name.
---

## Overview

This skill provides lightweight "search" helpers on the TSV files in the SEC 13F dataset.

**Dataset layout:** by default scripts read from `/root/<quarter>/` (e.g. `/root/2025-q3/COVERPAGE.tsv`).
You can override the dataset root with the `SEC_13F_DATA_ROOT` environment variable.

**Path convention:** commands below assume your working directory is the repository root.

## Usage

### Fuzzy search a fund using its name

```bash
python3 skills/fuzzy-name-search/scripts/search_fund.py \
  --keywords "bridgewater" \
  --quarter 2025-q2 \
  --topk 10
```

Results include the best-matching filings and their `ACCESSION_NUMBER`, which you can pass into the 13F analyzer.

### Exact search a fund using an accession number

```bash
python3 skills/fuzzy-name-search/scripts/search_fund.py \
  --accession_number 0000000000-00-000000 \
  --quarter 2025-q2
```

### Fuzzy search a stock CUSIP using issuer name

```bash
python3 skills/fuzzy-name-search/scripts/search_stock_cusip.py \
  --keywords palantir \
  --quarter 2025-q3 \
  --topk 10
```

The script normalizes CUSIPs to uppercase and filters to common-equity rows (excludes options when `PUTCALL` is present).

Normalize selected CUSIPs to uppercase and confirm the chosen CUSIP occurs in the requested quarter's `INFOTABLE`. If a name maps to both common equity and option positions, a request for the stock means the non-option common-equity CUSIP; do not substitute a Call or Put position.
