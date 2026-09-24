---
name: fuzzy-name-search
description: Fuzzy-search fund filings (COVERPAGE) by manager name and fuzzy-search
  stock CUSIPs by issuer name.
---

## Steps
1. **Fuzzy search a fund (COVERPAGE) by manager name** and pick the best match by score + name sanity-check:
   ```bash
   python3 scripts/search_fund.py --keywords "renaissance technologies" --quarter 2025-q3 --topk 10
   ```
   *Practical tip:* use consistent casing in your query (e.g., all-lowercase keywords) and verify the returned `FILINGMANAGER_NAME` matches the intended manager before using its `ACCESSION_NUMBER`.
2. **Exact search a fund when you already have an accession number** (to confirm you’ve got the right filing):
   ```bash
   python3 scripts/search_fund.py --accession_number <accession> --quarter 2025-q3
   ```
3. **Fuzzy search a stock CUSIP by issuer name** and use the top match CUSIP (normalize to uppercase when reusing it elsewhere):
   ```bash
   python3 scripts/search_stock_cusip.py --keywords "palantir" --topk 10
   ```
4. **When validating/aggregating holdings for a stock CUSIP (if you do any manual dataframe work):**
   - Normalize CUSIP casing (e.g., `str.upper()`).
   - Treat `PUTCALL` safely (e.g., `fillna('')`) to avoid mixed `NaN`/string issues during sorting/grouping.
   - For common-stock-only analyses, exclude option rows by requiring `PUTCALL == ''` (or equivalent “no put/call” indicator) before summing values.
## Expected Result
You can reliably retrieve the correct `ACCESSION_NUMBER` for a manager via COVERPAGE fuzzy search, retrieve/confirm a stock’s CUSIP via issuer-name search, and avoid common pitfalls from inconsistent casing and `PUTCALL` null/option rows when doing downstream aggregation.
