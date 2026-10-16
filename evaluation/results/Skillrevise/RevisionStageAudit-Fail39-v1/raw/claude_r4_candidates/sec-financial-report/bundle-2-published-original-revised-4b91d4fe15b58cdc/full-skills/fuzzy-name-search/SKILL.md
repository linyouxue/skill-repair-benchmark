# fuzzy-name-search

## Purpose
Resolve a 13F fund manager or stock issuer from an inexact name to a canonical record (accession number, CUSIP) and prepare that record for downstream aggregation. The skill wraps two fuzzy search scripts and adds the filtering, de-duplication, and cross-check rules needed before using results in holdings or ranking tasks.

## When to Use
Use when a task requires locating a 13F filer, selecting the correct accession for a given quarter, or mapping a stock name to a CUSIP, and the input name may be inexact. Do not use when an exact accession or CUSIP is already given and no quarter/amendment disambiguation is needed.

## Procedure
- Discover tool paths and data roots: `find / -name search_fund.py -o -name search_stock_cusip.py 2>/dev/null` and locate the quarter data directory (e.g., a path containing `COVERPAGE.tsv`, `INFOTABLE.tsv`, `SUMMARYPAGE.tsv` for the target quarter). Use the discovered absolute paths; do not assume `scripts/...`.
- Run fuzzy search with `--topk` large enough (>=20) to avoid display truncation. For funds: pass `--keywords <name> --quarter <YYYY-qN>`. For stocks: pass `--keywords <name>`.
- Filter candidates: keep rows where `REPORTCALENDARORQUARTER` equals the target quarter-end date and `ISAMENDMENT` is false unless an amendment is explicitly required; when multiple accessions share a manager, prefer `REPORTTYPE = 13F HOLDINGS REPORT`. Deduplicate issuer rows by `(NAME, CUSIP)`.
- Confirm the chosen accession by grepping the discovered `COVERPAGE.tsv` for the manager name, then cross-check its `INFOTABLE` row count and value sum against `SUMMARYPAGE` fields `TABLEENTRYTOTAL` and `TABLEVALUETOTAL`.
- If fuzzy top-1 is ambiguous or appears truncated, fall back to `grep -i "<name>" <discovered COVERPAGE.tsv>` before concluding no match.

## Constraints / Pitfalls
- Do not hardcode script or data paths; discover them each run. Relative `scripts/...` references are not reliable.
- Do not treat raw filer row counts as distinct fund managers; collapse amendments and duplicate filings per manager before ranking or counting.
- Do not aggregate holdings across accessions without first applying the quarter and amendment filters; mixing original and amended filings inflates totals.
- Keep only one accession per (manager, quarter) unless the task explicitly asks about amendments.
- Do not paste raw ranked search dumps into downstream reasoning; extract only the selected accession/CUSIP plus confirmation fields.