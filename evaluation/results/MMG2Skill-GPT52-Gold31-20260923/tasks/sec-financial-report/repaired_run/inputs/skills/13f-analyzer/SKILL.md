---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F filings to obtain insights
  such as number of holdings, total reported 13F value, and changes between two quarters.
---

## Steps
1. **Analyze one fund in one quarter (fund totals + holdings counts)** using the fund’s `accession_number`:
   ```bash
   python3 scripts/one_fund_analysis.py \
       --accession_number <accession> \
       --quarter 2025-q3
   ```
2. **Interpretation for “AUM” questions:** use the filing’s **SUMMARYPAGE `TABLEVALUETOTAL`** as the *total reported market value of 13F securities* (often used as an AUM proxy in 13F datasets; it is not necessarily the manager’s full firm-wide AUM).
3. **Number of stocks held:** use the fund’s holdings list and count **unique CUSIPs** (for most managers this should align with `TABLEENTRYTOTAL`, but use unique CUSIPs as the definitive “how many stocks” answer).
4. **Compare a fund between Q2 and Q3 (delta / increases / decreases)**:
   ```bash
   python3 scripts/one_fund_analysis.py \
       --quarter 2025-q3 \
       --accession_number <q3_accession> \
       --baseline_quarter 2025-q2 \
       --baseline_accession_number <q2_accession>
   ```
5. **If multiple filings exist for the same manager in a quarter (e.g., amendment vs original):** prefer the accession whose SUMMARYPAGE shows the *full filing* (typically much larger `TABLEENTRYTOTAL` and `TABLEVALUETOTAL`) before computing quarter-to-quarter deltas.
6. **Find top holders of a given stock in a quarter** (for manager ranking questions):
   ```bash
   python3 scripts/holding_analysis.py \
       --cusip <CUSIP> \
       --quarter 2025-q3 \
       --topk 10
   ```
## Expected Result
You can (a) retrieve a fund’s SUMMARYPAGE totals (including `TABLEVALUETOTAL`) and holdings counts, (b) compute Q2→Q3 holding/value deltas for a specific manager, and (c) list the largest holders (by reported 13F value) for a given CUSIP.
