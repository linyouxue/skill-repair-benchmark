---
name: fuzzy-name-search
description: Fuzzy search 13F COVERPAGE filings for fund accession numbers and look
  up stock CUSIPs by issuer name.
---

## Steps
1. From the workspace root (the directory that contains `fuzzy-name-search/`), confirm the scripts are where you’ll call them from:
   ```bash
   ls fuzzy-name-search/scripts/
   ```
2. Fuzzy search a fund in a specific quarter’s `COVERPAGE.tsv` to obtain the quarter-specific `ACCESSION_NUMBER`:
   ```bash
   python3 fuzzy-name-search/scripts/search_fund.py \
     --keywords "renaissance technologies" \
     --quarter 2025-q3 \
     --topk 10
   ```
   Review the ranked matches, normalize case/whitespace mentally, and select the best match by manager name/address. Accession numbers are filing IDs—repeat this lookup independently for each quarter; do not reuse a Q2 accession number for Q3.
3. If you already have an accession number (e.g., from holdings ranking) and need the manager name, do an exact lookup in the same quarter:
   ```bash
   python3 fuzzy-name-search/scripts/search_fund.py \
     --accession_number <ACCESSION_NUMBER> \
     --quarter 2025-q3
   ```
   Prefer a non-amendment filing when there are multiple related entries.
4. Fuzzy search a stock’s CUSIP by issuer name:
   ```bash
   python3 fuzzy-name-search/scripts/search_stock_cusip.py \
     --keywords "palantir" \
     --topk 10
   ```
   Normalize the chosen CUSIP to uppercase, and confirm it appears in the target quarter’s `INFOTABLE.tsv`. If a name corresponds to both common equity and options, “the stock” means the non-option common-equity CUSIP (do not substitute Call/Put positions).

## Expected Result
You obtain the correct quarter-specific `ACCESSION_NUMBER`(s) for target funds and the correct stock `CUSIP`(s), ready to be fed into the `13f-analyzer` scripts for AUM/holding-count extraction and Q2→Q3 comparisons.
