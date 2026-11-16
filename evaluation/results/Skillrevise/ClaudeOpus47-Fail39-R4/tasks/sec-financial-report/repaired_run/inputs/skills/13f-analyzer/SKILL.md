# 13f-analyzer

## Purpose
Perform reusable analyses over SEC Form 13F filings laid out as TSV tables per quarter: single-fund quarterly summary (AUM, holding counts), two-quarter holding deltas (buys and sells by notional), and ranking funds by exposure to a given stock. The skill operates directly on the raw 13F TSVs (COVERPAGE, SUMMARYPAGE, INFOTABLE) rather than any bespoke helper script.

## When to Use
Trigger when the task asks for quantitative insights about 13F filers for a specific quarter or across two quarters, including: fund-level AUM or holding counts, newly bought or sold positions between quarters, or which funds hold a particular stock (by CUSIP or issuer name). Do not trigger for non-13F SEC data or for narrative filings (10-K, 10-Q, 8-K).

## Procedure
- Discover the environment first. List the quarter directory supplied by the task (e.g. a path shaped like `<root>/<YYYY>-q<N>`) and confirm that `COVERPAGE.tsv`, `SUMMARYPAGE.tsv`, and `INFOTABLE.tsv` exist. Run `head -1` on each to record the exact column names; do not assume column names from memory. If files are missing or named differently, search the provided workspace (`find <root> -name 'INFOTABLE*'`) and adapt. Do not invoke any script that has not been verified to exist.
- Resolve the fund (ACCESSION_NUMBER). If the task gives an accession number, use it directly. Otherwise, read `COVERPAGE.tsv` and fuzzy-match on `FILINGMANAGER_NAME` (lowercased, punctuation-stripped); inspect the top-k candidates and their `CIK`, `ISAMENDMENT`, and `AMENDMENTTYPE`. Resolution rule: for a given (CIK, PERIODOFREPORT), prefer the latest `AMENDMENTTYPE = RESTATEMENT` filing if present; otherwise use the original (`ISAMENDMENT = false`) filing. Never silently pick the first match.
- Define metrics explicitly before computing:
- AUM for a filing: `SUMMARYPAGE.TABLEVALUETOTAL` for that ACCESSION_NUMBER (verify units from the column header; 13F values are typically reported in whole dollars for post-2022 filings and in thousands before).
- Number of entries: `SUMMARYPAGE.TABLEENTRYTOTAL` or `COUNT(*)` on INFOTABLE for the accession.
- Number of stock holdings: count of DISTINCT `CUSIP` in INFOTABLE for the accession where `PUTCALL` is NULL or empty (exclude options). Report both the entry count and the unique-CUSIP count when they differ.
- For two-quarter deltas, resolve both accessions using the rule above, load INFOTABLE rows for each (equity-only: `PUTCALL` blank), aggregate `VALUE` per CUSIP, then compute set differences: new buys = CUSIPs in later quarter not in earlier; full sells = CUSIPs in earlier not in later; rank each by the aggregated `VALUE` in the quarter where they appear.
- For top-holders-of-a-stock, first disambiguate the stock. If given an issuer name, enumerate all CUSIPs in INFOTABLE whose associated `NAMEOFISSUER` matches (case-insensitive) and list the share classes (`TITLEOFCLASS`) and CUSIPs found; if multiple classes exist (e.g., Class A vs Class B), either sum across them or restrict to the class specified by the task, and state the choice explicitly. Filter to `PUTCALL` blank. Aggregate `VALUE` per ACCESSION_NUMBER, join to COVERPAGE on ACCESSION_NUMBER to get `FILINGMANAGER_NAME`, and return the top-k by aggregated value.
- Validate before reporting. Reload the final frames and assert: non-empty result, numeric columns are numeric, no NaN in ranking key, and that the row counts after PUTCALL filter are strictly less than or equal to raw row counts. Print the raw-vs-filtered counts as a sanity log.

## Constraints / Pitfalls
- Do not reference or invoke scripts that have not been verified to exist in the current environment. Treat `scripts/*.py` paths as examples only; always fall back to direct TSV reads (pandas with `sep='\t'`, `dtype=str` initially, then cast numeric columns).
- Do not sum `VALUE` across rows where `PUTCALL` is `Put` or `Call` when measuring stock ownership; options exposure is not equivalent to share ownership.
- Do not pick the first fuzzy name match without inspecting amendment status. Always apply the original-vs-restatement rule and record which was chosen.
- Do not conflate "number of entries" (INFOTABLE rows or `TABLEENTRYTOTAL`) with "number of stock holdings" (unique equity CUSIPs). State which definition is used.
- Do not assume a single CUSIP per issuer. For issuers with multiple share classes, enumerate CUSIPs from INFOTABLE, decide aggregation vs selection explicitly, and document the choice in the output.
- Do not hard-code quarter paths, column indices, or value-unit assumptions. Derive them from the discovery step for the specific run.
- If the task specifies an output file or format, write to the exact path given and re-read it to confirm existence and schema before declaring completion.