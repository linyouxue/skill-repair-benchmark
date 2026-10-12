---
name: 13f-analyzer
description: Use repository scripts to analyze SEC 13F filings for fund totals, holdings counts, quarter changes, and top holders with benchmark-consistent semantics.
---

## Plan and verify before computing

1. Classify the question into one of: **fund totals / holdings count**, **quarter-over-quarter deltas**, **top holders of a security**; then choose the matching repository script.
2. Hard-stop: do not compute metrics manually until you have either (a) run the relevant `scripts/*.py` CLI successfully, or (b) written a manual replication plan that matches the script’s semantics (field meaning, filters/dedup, filing-selection policy, units).
3. If scripts are not found immediately, confirm you are at the repo/workspace root, then search from *your current directory* (not a guessed path) and verify the files exist before continuing.
4. Before writing any numbers, confirm metric meaning and units by inspecting script output or code (e.g., “AUM” vs 13F holdings value; “stocks” vs distinct holdings vs line items; $ vs $ thousands).
5. When comparing quarters, apply a consistent filing selection rule across quarters (often “latest amendment for that quarter” unless the question requests original).

Read references/13f-script-first.md when you have not yet located or run the repo’s 13F scripts, or when the prompt’s metric terms are ambiguous (“AUM”, “stocks held”, “share value”). Skip when the task explicitly forbids running provided scripts and you already have a written replication plan.

## Fund-level summary and quarter-over-quarter deltas

Use `one_fund_analysis.py` for fund totals and change analysis; it encodes benchmark definitions for totals, holdings count, quarter baselines, filing selection, and filtering/dedup.

```bash
python3 scripts/one_fund_analysis.py \
  --quarter <quarter> \
  --accession_number <accession>
```

Decision rule: If the question uses words like “AUM”, “how many stocks/holdings”, “largest purchases/sales”, or “change from Qx to Qy”, start here rather than aggregating raw 13F TSV fields.

## Top holders of a security (by the requested basis)

Use `search_stock_cusip.py` to obtain a canonical CUSIP, then run `holding_analysis.py` to rank holders using the benchmark’s basis and filters.

```bash
python3 scripts/holding_analysis.py \
  --cusip <cusip> \
  --quarter <quarter> \
  --topk <k>
```

Decision rule: If the prompt’s ranking basis is ambiguous (“share value” vs “market value”), treat that as a script-semantic question and resolve it by reading script output/code before producing results.

## Common Pitfalls

- Stopping script discovery too early and switching to ad-hoc parsing/fuzzy matching, which drifts from benchmark semantics.
- Outputting numerics without confirming field meaning and units/scaling (e.g., “AUM” vs 13F holdings value; $ vs $ thousands).
- Computing deltas across quarters while mixing original filings and amendments or using inconsistent filing-selection rules.
- Ranking top holders on the wrong basis (shares vs market value) or with inconsistent instrument filtering.
