---
name: fuzzy-name-search
description: Search capability in 13F datasets, such as fuzzy searching a fund (manager) by name, or fuzzy searching a stock CUSIP by issuer name.
---

## Overview

This tool provides a search interface over the local quarter datasets:

- `/root/2025-q2`
- `/root/2025-q3`

It supports fuzzy string search (RapidFuzz / Levenshtein-like scoring).

## Usage

### Fuzzy search a fund using its name

```bash
python3 scripts/search_fund.py --keywords "bridgewater" --quarter 2025-q2 --topk 10
```

The results include top-k funds with the most similar manager name and provide the associated `ACCESSION_NUMBER`.

### Exact search a fund using accession number

```bash
python3 scripts/search_fund.py \
  --accession_number 0001172661-25-003151 \
  --quarter 2025-q2
```

### Fuzzy search a stock CUSIP using issuer name

```bash
python3 scripts/search_stock_cusip.py \
  --keywords palantir \
  --quarter 2025-q3 \
  --topk 10
```

Notes:

- The stock search runs against the requested quarter’s `INFOTABLE`.
- CUSIPs are normalized to uppercase.
- If the dataset contains option lines (PUT/CALL), the search will ignore them (common-equity intent).
