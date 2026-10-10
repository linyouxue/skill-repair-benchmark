# 13F Analyzer

## Purpose
Produce defensible analytical answers over SEC Form 13F filings (per-fund summaries, cross-quarter holdings deltas, and top-funds-by-stock rankings) by working directly from the raw quarterly TSV dumps and validating every reported number against the filing's own declared totals.

## When to Use
Trigger when a task asks for insights about 13F filings in a dataset organized as per-quarter folders (for example YYYY-qN) containing COVERPAGE, SUMMARYPAGE, and INFOTABLE TSV files, and the question concerns a fund's AUM, number of holdings, holding changes between quarters, or ranking of funds by exposure to a given security.

## Procedure
- Discover: list the dataset root and each referenced quarter folder. Confirm that COVERPAGE.tsv, SUMMARYPAGE.tsv, and INFOTABLE.tsv (or case/suffix variants) are present. If any are missing, search sibling directories before proceeding; do not assume script wrappers exist.
- Validate schema: open the first lines of each TSV, confirm it is tab-delimited, and locate the columns actually needed: ACCESSION_NUMBER, FILINGMANAGER_NAME (COVERPAGE); ACCESSION_NUMBER, TABLEENTRYTOTAL, TABLEVALUETOTAL, ISCONFIDENTIALOMITTED (SUMMARYPAGE); ACCESSION_NUMBER, CUSIP, NAMEOFISSUER, VALUE, SSHPRNAMT, SSHPRNAMTTYPE, PUTCALL (INFOTABLE). Record units (13F VALUE is reported in whole dollars in recent years, thousands in older years; verify from the dataset's own documentation or by cross-checking SUMMARYPAGE.TABLEVALUETOTAL against INFOTABLE sums).
- Select filing(s): resolve the target fund by case-insensitive match on FILINGMANAGER_NAME (and/or a provided ACCESSION_NUMBER). If multiple ACCESSION_NUMBERs match for the same manager+quarter (amendments), prefer the latest/most-complete filing deliberately and document the rule used; never silently pick the first row.
- Aggregate: compute the requested metrics by grouping INFOTABLE rows on ACCESSION_NUMBER (and CUSIP where relevant). For holdings deltas, align two quarters on CUSIP after selecting one filing per quarter per manager.
- Cross-check: before reporting, assert that SUM(INFOTABLE.VALUE for the chosen ACCESSION_NUMBER) equals SUMMARYPAGE.TABLEVALUETOTAL and that COUNT(INFOTABLE rows) equals SUMMARYPAGE.TABLEENTRYTOTAL within a documented tolerance (allow for unit scaling). On mismatch, revisit filing selection or unit assumptions; do not finalize.
- Rank and interpret: for top-funds-by-stock queries, aggregate INFOTABLE.VALUE per ACCESSION_NUMBER filtered on CUSIP, join to COVERPAGE for manager names, then sort. If the question specifies a subset (for example hedge-fund managers vs all 13F filers), apply an explicit filter rule and state it; do not report a raw top-N when the question constrains the universe.
- Report: emit only metrics that passed the cross-check, together with the ACCESSION_NUMBER(s) used and the filter rules applied.

## Constraints / Pitfalls
- Do not invoke scripts or paths that have not been verified to exist; always discover the environment first.
- Do not submit answers without the SUMMARYPAGE vs INFOTABLE consistency check passing for every ACCESSION_NUMBER used.
- Do not conflate 13F filers with hedge funds: 13F includes index managers, banks, insurers, and advisors. When a question targets a specific manager type, apply and disclose an explicit filter; otherwise state that results cover all 13F filers.
- Handle amendments explicitly: multiple filings per manager per quarter are common; pick one rule (latest amendment, or original) and apply it consistently across both quarters in delta analyses.
- Verify VALUE units per dataset vintage before computing AUM; a 1000x error is the most common silent failure.
- Do not hard-code manager names, CUSIPs, ACCESSION_NUMBERs, quarter labels, or file paths from any single task instance into the procedure.