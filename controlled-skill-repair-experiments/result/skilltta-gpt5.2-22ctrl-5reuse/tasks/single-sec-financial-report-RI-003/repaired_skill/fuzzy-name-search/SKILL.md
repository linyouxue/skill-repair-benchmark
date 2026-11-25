---
name: fuzzy-name-search
description: Search capability in 13F, such as fuzzy search a fund using its name, or fuzzy search a stock CUSIP using a company name.
---

## Overview

This tool is a lightweight search engine over 13F-derived tables. You do not
need to provide an exact name; it uses fuzzy string matching.

The search helpers are installed under `/skills/fuzzy-name-search/scripts`,
while filing data lives under `/root/<quarter>`. Run the helpers from their
absolute `/skills/...` paths; do not look for them under `/root/scripts`.


## Usage

### Fuzzy search a fund using its name

```bash
python3 /skills/fuzzy-name-search/scripts/search_fund.py \
  --keywords '<manager keywords>' \
  --quarter 2025-q2 \
  --topk 10
```

Output fields depend on what the dataset provides, but typically include:
- `ACCESSION_NUMBER`
- `REPORTCALENDARORQUARTER`
- `FILINGMANAGER_NAME`

### Exact search a fund using accession number

```bash
python3 /skills/fuzzy-name-search/scripts/search_fund.py \
  --accession_number <accession_number> \
  --quarter 2025-q2
```

### Fuzzy search a stock using its name

Use the quarter that is relevant to your analysis so the search is consistent
with that quarter's holdings universe:

```bash
python3 /skills/fuzzy-name-search/scripts/search_stock_cusip.py \
  --keywords '<company name>' \
  --quarter 2025-q3 \
  --topk 10
```

The output prints candidate issuer names and their CUSIPs. Normalize CUSIPs to
uppercase and confirm the selected CUSIP occurs in the requested quarter's
`INFOTABLE`.

If a name maps to common equity and option positions, a request for the stock
normally means the non-option common-equity line; do not substitute a Call or
Put position.
