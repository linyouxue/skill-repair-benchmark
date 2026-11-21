---
name: fuzzy-name-search
description: This skill includes search capability in 13F, such as fuzzy search a fund information using possibly inaccurate name, or fuzzy search a stock cusip info using its name.
---

## Overview

This tool is essentially a search engine that provides you the ability to search a fund or stock meta information with a name. Note that you don't have to provide the accurate name since this tool has built-in fuzzy string search algorithms based on Levenshtein distance.

## Usage

### Fuzzy search a fund using its name

From the repo root, call:

```bash
python3 fuzzy-name-search/scripts/search_fund.py --keywords "bridgewater" --quarter 2025-q2 --topk 10
```

The results include top-k funds with names most similar to the query.

### Exact search a fund using accession number

```bash
python3 fuzzy-name-search/scripts/search_fund.py \
  --accession_number 0001172661-25-003151 \
  --quarter 2025-q2
```

### Fuzzy search a stock using its name

```bash
python3 fuzzy-name-search/scripts/search_stock_cusip.py \
  --keywords palantir \
  --topk 10
```

Normalize CUSIPs to uppercase and confirm the selected CUSIP occurs in the
requested quarter's `INFOTABLE`. If a name maps to common equity and option
positions, a request for the stock means the non-option common-equity CUSIP;
do not substitute a Call or Put position.
