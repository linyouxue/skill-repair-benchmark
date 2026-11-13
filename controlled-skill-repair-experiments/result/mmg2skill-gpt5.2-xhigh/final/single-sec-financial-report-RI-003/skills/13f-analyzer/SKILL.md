---
name: 13f-analyzer
description: Perform analysis on SEC 13F filings to get per-fund AUM/holding counts,
  and quarter-over-quarter “Top Buys/Sells” changes.
---

## Steps
1. Use the helper scripts from their absolute path under `/skills/13f-analyzer/scripts` (the task data is under `/root/<quarter>`, so `/root/scripts/...` is not the same location). If a helper “is missing”, check `/skills/13f-analyzer/scripts` before building a replacement pipeline.

2. After you have a fund’s `ACCESSION_NUMBER` for a given quarter, get one-quarter summary stats (AUM, holding counts):
   ```bash
   python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
     --accession_number <ACCESSION_NUMBER> \
     --quarter 2025-q3
   ```

3. Interpret the printed fields precisely:
   - `Total AUM` = sum of `VALUE` across all reported rows for that accession filing.
   - `Number of stock holdings` = number of rows remaining after the script’s `TITLEOFCLASS` stock filter; when asked “how many stocks”, use this field (not `Total number of holdings`, `TABLEENTRYTOTAL`, or a unique-CUSIP count).

4. For cross-quarter change / “Top Buys” (e.g., Q2 → Q3 for the same manager, using quarter-specific accession numbers), run:
   ```bash
   python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
     --quarter 2025-q3 \
     --accession_number <Q3_ACCESSION_NUMBER> \
     --baseline_quarter 2025-q2 \
     --baseline_accession_number <Q2_ACCESSION_NUMBER>
   ```
   Use the `Top 10 Buys` section to answer “increased investment” questions:
   - It is ranked by `ABS_CHANGE = VALUE(Q3) - VALUE(Q2)` (dollar-value increase).
   - It includes both new positions and increases to existing positions.
   - Take the top 5 positive `ABS_CHANGE` rows when asked for “top 5 increases”.

5. To find the top holders of a stock CUSIP in a specific quarter (and get **manager names**, not just accession numbers), aggregate that quarter’s `/root/<quarter>/INFOTABLE.tsv` by `ACCESSION_NUMBER` and join to `/root/<quarter>/COVERPAGE.tsv`:
   ```bash
   python3 - <<'PY'
   import pandas as pd

   quarter = "2025-q3"
   cusip = "69608A108"
   topk = 10

   inf = pd.read_csv(f"/root/{quarter}/INFOTABLE.tsv", sep="\t", dtype=str)
   inf["CUSIP"] = inf["CUSIP"].str.upper()
   inf["VALUE"] = inf["VALUE"].astype(float)
   if "PUTCALL" in inf.columns:
       inf = inf[inf["PUTCALL"].isna() | (inf["PUTCALL"] == "")]

   g = (inf[inf["CUSIP"] == cusip]
        .groupby("ACCESSION_NUMBER", as_index=False)["VALUE"].sum()
        .sort_values("VALUE", ascending=False)
        .head(topk))

   cover = pd.read_csv(f"/root/{quarter}/COVERPAGE.tsv", sep="\t", dtype=str)[
       ["ACCESSION_NUMBER", "FILINGMANAGER_NAME"]
   ].drop_duplicates()

   out = g.merge(cover, on="ACCESSION_NUMBER", how="left")
   print(out[["ACCESSION_NUMBER", "FILINGMANAGER_NAME", "VALUE"]].to_string(index=False))
   PY
   ```

## Expected Result
- You can extract a fund’s quarter AUM and “number of stock holdings” from a single 13F filing.
- You can compute and read quarter-over-quarter “Top Buys” ranked by dollar-value increase (`ABS_CHANGE`), and select the top N CUSIPs.
- You can rank top holders of a given CUSIP in a quarter by total `VALUE`, and resolve accession numbers to filing manager names via `COVERPAGE.tsv`.
