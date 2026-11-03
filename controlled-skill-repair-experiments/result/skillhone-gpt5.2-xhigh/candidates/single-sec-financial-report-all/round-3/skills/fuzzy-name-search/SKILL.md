---
name: fuzzy-name-search
description: Search helpers for SEC 13F datasets: fuzzy fund lookup via COVERPAGE and fuzzy stock/CUSIP lookup via INFOTABLE.
---

## Overview

This skill provides two small command-line utilities:

- `scripts/search_fund.py`: fuzzy (or exact) search for funds/managers in `COVERPAGE.tsv`
- `scripts/search_stock_cusip.py`: fuzzy search for issuer names and return candidate CUSIPs from `INFOTABLE.tsv`

The dataset is expected at:

- `${DATA_ROOT}/${QUARTER}/COVERPAGE.tsv`
- `${DATA_ROOT}/${QUARTER}/INFOTABLE.tsv`

Where `${QUARTER}` is a folder like `2025-q3`.

### Path / working-directory convention

You can run the scripts either:

- From the skill directory:
  ```bash
  cd skills/fuzzy-name-search
  python3 scripts/search_fund.py ...
  ```

- Or from the repo root (use the full path):
  ```bash
  python3 skills/fuzzy-name-search/scripts/search_fund.py ...
  ```

All commands below assume you are in `skills/fuzzy-name-search`.

## Usage

### 1) Fuzzy search a fund using its name

```bash
python3 scripts/search_fund.py --keywords "bridgewater" --quarter 2025-q2 --topk 10
```

This prints the top matches by fuzzy score (WRatio).

### 2) Exact search a fund using accession number

```bash
python3 scripts/search_fund.py \
  --accession_number 0001172661-25-003151 \
  --quarter 2025-q2
```

### 3) Fuzzy search a stock CUSIP using its name

```bash
python3 scripts/search_stock_cusip.py \
  --keywords "palantir" \
  --quarter 2025-q3 \
  --topk 10 \
  --data_root /root
```

Notes:

- CUSIPs are normalized to **uppercase**.
- Prefer **common-equity (non-option)** rows when the dataset contains both common equity and option legs.
- Confirm the selected CUSIP occurs in the requested quarter’s `INFOTABLE.tsv`.
