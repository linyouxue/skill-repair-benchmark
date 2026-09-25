# SKILL.md

## When to use
Use this skill when you must answer specific quantitative questions from a local, quarter-partitioned regulatory/holdings dataset (e.g., two folders representing different reporting quarters). The contract typically requires:
- Locating an entity/fund via **fuzzy search** over a “cover page / filer / fund metadata” table.
- Using the resulting **accession identifier** to load fund details (AUM, holdings list, etc.).
- Comparing **holdings across two quarters** to compute changes and rank results.
- Producing a strict-output artifact (here: a JSON file at a specified path with a fixed schema).

Before acting, gather evidence about:
- Directory structure and file types in each quarter folder (CSV/JSON/Parquet/SQLite, etc.).
- Where “cover page” data lives and what fields identify a fund (name, manager, CIK, accession number).
- Where holdings live and what fields define a position (CUSIP/ticker, shares, value, issuer name).
- Whether “value” is already in dollars (preferred) or must be derived (e.g., shares × price).

## Possible Failure Modes
- **Using the wrong entity due to fuzzy-match ambiguity** (similar fund names, adviser vs. fund name, multiple share classes, feeder/master).
- **Mixing quarter sources** (accidentally reading Q2 files while answering a Q3-only question or vice versa).
- **Incorrect join key**: assuming accession number matches across tables when the dataset actually uses another key (CIK + accession, filing id, report id).
- **Wrong AUM field**: confusing AUM with “total value of holdings” or another aggregate.
- **Counting “stocks held” incorrectly**: counting rows (can include duplicates, options, or multiple lots) instead of counting distinct equity CUSIPs; or including non-stock holdings when the question expects stocks only.
- **Ranking “increased investment” incorrectly**:
  - ranking by share change instead of **dollar value increase**,
  - failing to align by CUSIP across quarters,
  - mishandling new positions (Q2 = 0) or disposed positions (negative changes),
  - not filtering to **increases only**.
- **CUSIP formatting issues**: dropping leading zeros, whitespace, inconsistent length; returning tickers instead of CUSIPs.
- **Palantir lookup mismatch**: selecting the wrong security (different issuer names, ADRs, multiple CUSIPs) or failing to resolve CUSIP before aggregation.
- **Output/schema mismatch**: wrong JSON keys, numbers serialized as strings, incorrect list lengths, writing to wrong path.

## Possible procedures
1. **Inventory the data layout**
   - List files in each quarter folder; identify metadata (“coverpage”) and holdings datasets.
   - Determine whether the data is stored as flat files or a database (e.g., SQLite). If SQLite, prefer `pandas.read_sql_query` with safe connection handling (open → query → close).

2. **Load cover page / filer index for the target quarter**
   - Read the coverpage-equivalent table for Q3.
   - Identify columns likely containing the fund/manager name and the accession identifier.

3. **Fuzzy-search the fund name (robustly)**
   - Normalize text (lowercase, strip punctuation/extra whitespace).
   - Compute similarity against relevant name columns (fund name, adviser name, reporting manager).
   - Inspect the top matches (not just the best score); choose the match consistent with the question’s description.
   - Record the selected **accession number** for downstream queries.

4. **Obtain fund details (AUM) from the accession number**
   - Using the accession number, load the fund detail record(s).
   - Identify the correct AUM field (confirm units and whether it’s numeric).
   - If multiple rows exist for the accession, determine if they must be aggregated or if one row is authoritative (use documentation/field names as evidence).

5. **Compute “how many stocks are held” (Q3)**
   - Load Q3 holdings for the selected accession number.
   - Decide what counts as a “stock” based on available fields:
     - Prefer filtering to equity/common stock if a “security type/class/title” field exists.
     - Otherwise, approximate by excluding obvious non-stocks (options, notes) if labeled.
   - Count **distinct** stock identifiers (prefer CUSIP) after normalization (strip, pad/keep leading zeros as text).

6. **Berkshire Q2→Q3: top 5 increased investments by dollar value**
   - Repeat the coverpage fuzzy-search independently in **Q2** and **Q3** to get two accession numbers (do not assume they stay constant).
   - Load holdings for both accessions.
   - Normalize keys (CUSIP as string, standardized formatting).
   - Build per-quarter aggregates by CUSIP:
     - total value (preferred), optionally total shares as supporting evidence.
   - Compute `delta_value = value_q3 - value_q2` with missing treated as 0.
   - Filter to `delta_value > 0`, sort descending, take top 5 CUSIPs.
   - Recovery check: ensure you did not accidentally sort by absolute value or include negative/zero deltas.

7. **Top-3 fund managers holding Palantir (Q3) by share value**
   - Resolve Palantir’s CUSIP using the dataset’s security master / holdings reference:
     - Search by issuer name (case-insensitive, fuzzy).
     - Confirm by checking consistent ticker/issuer fields if available.
   - In Q3 holdings across all managers/funds:
     - Filter positions where CUSIP equals Palantir’s CUSIP.
     - Aggregate by manager/fund name using **value** (share value/dollar value field).
     - Rank descending; output the top 3 manager names as they appear in coverpage/manager metadata.
   - If holdings don’t include manager name, join holdings to coverpage via accession (or equivalent) first.

8. **Write results to `/root/answers.json`**
   - Construct an object with exactly the required keys.
   - Ensure numeric fields are JSON numbers (not quoted), list lengths match requirements, and strings are CUSIPs / manager names (not internal ids).
   - Write the file to the exact path required.

## Verification Checklist
- [ ] Confirm you only used Q3 data for Q1, Q2, and Q4; and both Q2+Q3 for Q3 comparison.
- [ ] Fuzzy-match selection is justified: you inspected top candidates and chose the correct entity, not merely the highest raw score.
- [ ] Accession numbers used for each quarter were obtained from that quarter’s coverpage (no reuse across quarters unless verified).
- [ ] AUM extracted from the correct “fund details” source and is numeric with correct units (no string/commas; no accidental holdings-sum substitution).
- [ ] “Number of stocks held” is computed as a **distinct count** of stock identifiers (and you handled duplicates/formatting).
- [ ] Berkshire top-5 list is ranked by **positive dollar value increase** (`q3 - q2`), returns **CUSIPs**, and contains exactly 5 elements.
- [ ] Palantir CUSIP resolution is verified (issuer/ticker cross-check if available), and top-3 managers are ranked by value and contain exactly 3 names.
- [ ] `answers.json` exists at `/root/answers.json`, matches the required schema/keys exactly, and uses correct JSON types.
- [ ] You did not copy concrete identifiers/values from any retrieved examples; you preserved unrelated files/state and only wrote the required output file.
- [ ] If any table/column ambiguity arose, you recorded/checked evidence (sample rows, column meanings) and reran computations after correcting joins/filters.
