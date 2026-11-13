---
name: fuzzy-name-search
description: Fuzzy-search funds in 13F COVERPAGE data and fuzzy-search stock CUSIPs
  by issuer name.
---

## Steps
1. Run the search helpers from their absolute path under `/skills/fuzzy-name-search/scripts` (data lives under `/root/<quarter>`).

2. Fuzzy-search a fund by name within a specific quarter’s `COVERPAGE.tsv`:
   ```bash
   python3 /skills/fuzzy-name-search/scripts/search_fund.py \
     --keywords "renaissance technologies" \
     --quarter 2025-q3 \
     --topk 10
   ```
   Repeat per quarter when you need quarter-specific accession numbers (they change across reporting periods).

3. If the expected filer does not show up in the fuzzy results, scan the quarter’s `COVERPAGE.tsv` directly (this avoids missing rows when `ISAMENDMENT` is blank/NaN):
   ```bash
   python3 - <<'PY'
   import pandas as pd

   quarter = "2025-q3"
   kw = "renaissance technologies"

   cp = pd.read_csv(f"/root/{quarter}/COVERPAGE.tsv", sep="\t", dtype=str)
   m = cp[cp["FILINGMANAGER_NAME"].str.contains(kw, case=False, na=False)]
   print(m[["ACCESSION_NUMBER","FILINGMANAGER_NAME","REPORTCALENDARORQUARTER","ISAMENDMENT"]]
         .head(20).to_string(index=False))
   PY
   ```
   Choose the best match and record its `ACCESSION_NUMBER`.

4. Confirm a chosen accession number via exact lookup:
   ```bash
   python3 /skills/fuzzy-name-search/scripts/search_fund.py \
     --accession_number <ACCESSION_NUMBER> \
     --quarter 2025-q3
   ```

5. Fuzzy-search a stock CUSIP by issuer name:
   ```bash
   python3 /skills/fuzzy-name-search/scripts/search_stock_cusip.py \
     --keywords palantir \
     --topk 10
   ```
   Normalize the chosen CUSIP to uppercase and confirm it exists in the requested quarter’s `/root/<quarter>/INFOTABLE.tsv`. If both common equity and option positions appear, use the non-option common-equity position for “the stock”.

## Expected Result
- You can reliably obtain a fund’s quarter-specific `ACCESSION_NUMBER` even when fuzzy search misses the intended row.
- You can obtain a stock’s common-equity CUSIP from issuer-name keywords and validate it against the target quarter’s INFOTABLE data.
