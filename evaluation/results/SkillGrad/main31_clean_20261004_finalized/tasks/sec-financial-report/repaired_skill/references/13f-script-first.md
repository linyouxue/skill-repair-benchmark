# Script-first workflow for SEC 13F metrics

Use this procedure when a repo provides `scripts/search_fund.py`, `scripts/search_stock_cusip.py`, `scripts/one_fund_analysis.py`, or `scripts/holding_analysis.py`, and the task asks for totals, counts, deltas, or top holders.

## 1) Locate the scripts (do not guess paths)

```bash
pwd
ls
find . -maxdepth 5 -type f \( \
  -name 'search_fund.py' -o \
  -name 'search_stock_cusip.py' -o \
  -name 'one_fund_analysis.py' -o \
  -name 'holding_analysis.py' \
\) -print
```

Runtime branch:
- If `find` returns hits: use those exact paths.
- If `find` returns nothing: broaden the search scope (e.g., `find .. -maxdepth 8 ...`) and re-run; do not start manual parsing yet.

Verification:
- If you still cannot locate scripts after broadening search, stop and switch to a manual replication plan (Section 4); do **not** proceed with ad-hoc computations.

## 2) Resolve canonical identifiers (fund accession / stock CUSIP)

```python
import subprocess

def run(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True)

# Fund: keywords -> accession candidates
fund_out = run("python3 scripts/search_fund.py --keywords '...' --quarter ... --topk 10")

# Stock: keywords -> CUSIP candidates
stock_out = run("python3 scripts/search_stock_cusip.py --keywords '...' --topk 10")

print(fund_out.splitlines()[:10])
print(stock_out.splitlines()[:10])
```

Runtime branch:
- If multiple candidates appear: prefer the one that matches the legal entity name and quarter; then confirm by running `one_fund_analysis.py` for that accession and checking the header/metadata.
- If the task already provides an accession/CUSIP: skip search and validate by running the analysis script once.

Verification:
- If analysis output (next section) indicates the wrong filer/security, go back and choose a different candidate; do not “patch” by fuzzy matching in pandas.

## 3) Compute metrics via analysis scripts (semantics live here)

```bash
# Fund totals, holdings counts, and quarter deltas
python3 scripts/one_fund_analysis.py --quarter <quarter> --accession_number <accession>

# Top holders of a security
python3 scripts/holding_analysis.py --cusip <cusip> --quarter <quarter> --topk <k>
```

Runtime branch:
- If the task asks for quarter-over-quarter change: run the fund analysis for both quarters using the script’s filing-selection policy (often “latest amendment for the quarter”), then use the script’s reported deltas.
- If the task asks for “share value” / “value” ranking: follow the script’s ranking basis; do not assume `VALUE` (market value) vs `SSHPRNAMT` (shares).

Verification:
- If numbers look off by ~1,000× or units are unclear, inspect the analysis script or its README output formatting before answering.
- If a computed metric disagrees with a raw summary field, trust the script and record the semantic difference (“AUM vs total 13F holdings value”, “distinct holdings vs table entries”).

## 4) Manual fallback only (replication plan + checks)

If and only if scripts are unavailable or cannot produce the requested metric, write a replication plan that maps each question term to:
- **fields** (e.g., which table/column),
- **units/scaling** (e.g., thousands of dollars),
- **dedup/filtering** (distinct CUSIPs vs rows; options/PUTCALL handling),
- **filing-selection rule** (original vs amendment; consistent across quarters).

```python
# Minimal template for a replication plan you can implement and test.
plan = {
    "metric": "...",
    "fields": ["..."],
    "units": "...",
    "filters": {"putcall": "exclude", "type": "common"},
    "dedup": "...",
    "filing_selection": "latest_for_quarter",
}
print(plan)
```

Verification (required):
- Recompute the same metric two ways (e.g., script vs manual on a small sample, or independent aggregation choices) and ensure they match.
- If they do not match, stop and re-audit the plan’s units and dedup/filing-selection rules before producing final answers.
