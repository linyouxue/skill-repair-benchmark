---
name: 13f-analyzer
description: Analyze SEC 13F holdings (INFOTABLE) to compute a fund’s AUM, stock-holding
  count, quarter-over-quarter changes, and top holders of a given stock.
---

## Steps
1. From the workspace root (the directory that contains `13f-analyzer/`), verify inputs and helper scripts exist so you don’t waste time “finding” them:
   - Data: `/root/2025-q2/INFOTABLE.tsv`, `/root/2025-q2/COVERPAGE.tsv`, `/root/2025-q3/INFOTABLE.tsv`, `/root/2025-q3/COVERPAGE.tsv`
   - Scripts: `ls 13f-analyzer/scripts/`
2. To get one fund’s summary in a single quarter (AUM and stock count), run:
   ```bash
   python3 13f-analyzer/scripts/one_fund_analysis.py \
     --accession_number <ACCESSION_NUMBER> \
     --quarter 2025-q3
   ```
   Interpret the printed fields precisely:
   - `Total AUM` = sum of `VALUE` across all rows for that accession number (use this for “AUM”).
   - `Number of stock holdings` = row-count after the helper’s `TITLEOFCLASS` stock filter. When asked “how many stocks”, use this field (not `Total number of holdings`, not unique CUSIPs, not COVERPAGE totals).
3. To compare a fund between quarters and get the biggest dollar-value increases (top buys), run:
   ```bash
   python3 13f-analyzer/scripts/one_fund_analysis.py \
     --quarter 2025-q3 \
     --accession_number <Q3_ACCESSION_NUMBER> \
     --baseline_quarter 2025-q2 \
     --baseline_accession_number <Q2_ACCESSION_NUMBER>
   ```
   For a request “ranked by dollar value increase”, take the required number of CUSIPs from the beginning of the helper’s `Top 10 Buys` section, preserving order (don’t re-rank by shares or % change). Verify you return exactly *k* unique CUSIP strings.
4. To rank which funds hold a given stock CUSIP by notional value, first follow the helper’s file-path convention (it reads `/root/INFOTABLE.tsv`, not `/root/<quarter>/INFOTABLE.tsv`):
   ```bash
   ln -sf /root/2025-q3/INFOTABLE.tsv /root/INFOTABLE.tsv
   python3 13f-analyzer/scripts/holding_analysis.py \
     --cusip <CUSIP> \
     --quarter 2025-q3 \
     --topk 10
   ```
   The output is ranked by summed `VALUE` per `ACCESSION_NUMBER`. Convert the top accession numbers to manager names using `fuzzy-name-search`’s exact accession-number lookup.
5. When the task requires a deliverable file, write the final numbers/lists into **`/root/answers.json`** (absolute path) using the required schema, and verify it exists (e.g., `ls -l /root/answers.json`).

## Expected Result
You can (a) extract a quarter’s fund AUM and stock-holding count from the helper’s printed summary, (b) extract top buy CUSIPs from the helper’s Q2→Q3 comparison output, (c) rank top holders of a CUSIP in Q3 and map accession numbers to manager names, and (d) populate `/root/answers.json` with the required fields.
