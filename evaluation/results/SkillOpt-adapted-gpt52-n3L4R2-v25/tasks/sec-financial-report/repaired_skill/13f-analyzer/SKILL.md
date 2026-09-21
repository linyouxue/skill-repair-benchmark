---
name: 13f-analyzer
description: Perform various data analysis on SEC 13-F and obtain some insights of fund activities such as number of holdings, AUM, and change of holdings between two quarters.
---

## Overview

### Analyze the holding summary of a particular fund in one quarter:

```bash
python3 scripts/one_fund_analysis.py \
    --accession_number ... \
    --quarter 2025-q2 \
```

Read the labeled fields from the one-fund output rather than inferring them: use the reported `AUM` field for assets under management and the reported `total number of stock holdings` field for the stock count. Do not substitute total holdings, option holdings, or the number of filing rows for the stock count.


### Analyze the change of holdings of a particular fund in between two quarters:

```bash
python scripts/one_fund_analysis.py \
    --quarter 2025-q3 \
    --accession_number <accession number assigned in q3> \
    --baseline_quarter 2025-q2 \
    --baseline_accession_number <accession number assigned in q2>
```

This script will print out the dynamic changes of holdings from 2025-q2 to 2025-q3. Such as newly purchased stocks ranked by notional value, and newly sold stocks ranked by notional value.


### Analyze which funds hold a stock to the most extent

```bash
python scripts/holding_analysis.py \
    --cusip <stock cusip> \
    --quarter 2025-q3 \
    --topk 10
```

This script will print out the top 10 hedge funds who hold a particular stock with highest notional value.



## Reproducible workflow for the 2025-Q3 financial-report task

Use the local datasets independently: `/root/2025-q2` for Q2 and `/root/2025-q3` for Q3. Run the scripts from the repository and, when a script exposes a data-root or input-directory option, point it at the corresponding quarter directory. Do not reuse an accession number between quarters.

1. Search the `COVERPAGE` records with the requested manager name and inspect the candidate manager name, reporting quarter, filing period, and accession number. Select the filing for Renaissance Technologies for Q3 2025 and separately select Berkshire Hathaway filings for Q2 2025 and Q3 2025. Validate every selected accession by querying it again in the same quarter and confirming both the manager identity and quarter before loading holdings.

2. For Renaissance, run `one_fund_analysis.py` with the verified Q3 accession and `--quarter 2025-q3`. Return the numeric value in the output field labeled `AUM` for q1, preserving its dollar units as a JSON number. Return the numeric value in the output field labeled `total number of stock holdings` for q2; this is an integer count and is distinct from total holdings.

3. For Berkshire, load the Q2 and Q3 holdings with their separately verified accessions. Normalize CUSIPs as strings so leading zeroes are retained, and join the two snapshots by CUSIP. For each CUSIP compute `Q3 dollar value - Q2 dollar value`; treat a missing Q2 position as zero for a new Q3 position and a missing Q3 position as zero for a position no longer held. Parse numeric values robustly (commas, currency symbols, and blank values), use the filing's reported position value/notional field rather than share count, retain only strictly positive increases, sort by the decrease/increase result descending, and return exactly the first five CUSIPs in q3_answer. The built-in dynamic-change output may be used as a check, but do not limit the calculation to newly purchased positions because existing positions can also have increased value.

4. Resolve Palantir independently by searching the Q3 security/CUSIP data for the issuer and validating the selected CUSIP against issuer and class metadata. Filter Q3 holdings to that exact CUSIP, group duplicate rows by the filing manager when necessary, and rank managers by share value/notional value (the reported dollar `VALUE` field; if unavailable, calculate shares multiplied by reported price). Do not rank by number of shares or by fund name alphabetically. Return exactly the top three manager-name values from the dataset's filing-manager name field in q4_answer.

5. Validate before writing `/root/answers.json`: q1_answer is a JSON number, q2_answer is an integer JSON number, q3_answer is an array of exactly five CUSIP strings, and q4_answer is an array of exactly three manager-name strings. Ensure all records came from the intended quarter/accession, preserve CUSIP leading zeroes, and emit only this schema with no explanatory prose:
```json
{
  "q1_answer": 0,
  "q2_answer": 0,
  "q3_answer": ["...", "...", "...", "...", "..."],
  "q4_answer": ["...", "...", "..."]
}
```
