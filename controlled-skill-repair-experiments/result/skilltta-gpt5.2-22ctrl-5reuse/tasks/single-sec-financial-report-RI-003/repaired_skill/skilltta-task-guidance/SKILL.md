---
name: skilltta-task-guidance
---

# 13F Cross-Quarter Analysis Workflow (Reusable)

This guide describes a reusable workflow to:
1) locate a filer via **COVERPAGE fuzzy search**,
2) load holdings via **ACCESSION_NUMBER**,
3) compute **AUM**, **#stocks**, **cross-quarter top increases**, and
4) rank **top holders of a target stock**.

Assumptions:
- Data are stored under `/root/<quarter>` (e.g., `/root/2025-q2`).
- Each quarter folder contains `COVERPAGE.tsv` and `INFOTABLE.tsv` (tab-separated).
- `VALUE` is often reported in $000; treat units as dataset-native unless you
  explicitly convert.


## 1) Find an accession number (filer) by fuzzy searching COVERPAGE

```bash
python3 /skills/fuzzy-name-search/scripts/search_fund.py \
  --keywords '<filer name keywords>' \
  --quarter <quarter> \
  --topk 10
```

Select the best match and copy its `ACCESSION_NUMBER`.


## 2) Fund-level summary in one quarter (AUM and stock count)

```bash
python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
  --accession_number <accession_number> \
  --quarter <quarter>
```

Use:
- `Total AUM` for AUM (dataset-native VALUE units).
- `Number of unique stock CUSIPs` for "how many stocks".


## 3) Cross-quarter comparison for one filer (Top Buys/Sells)

First obtain the accession number for the filer in **each** quarter (they can
change between reporting seasons). Then run:

```bash
python3 /skills/13f-analyzer/scripts/one_fund_analysis.py \
  --quarter <target_quarter> \
  --accession_number <target_accession> \
  --baseline_quarter <baseline_quarter> \
  --baseline_accession_number <baseline_accession>
```

The script ranks Top Buys/Sells by `ABS_CHANGE = VALUE_target - VALUE_baseline`
after stock filtering and aggregation by CUSIP.


## 4) Top holders of a target stock (manager names)

1) Discover the stock CUSIP by name:

```bash
python3 /skills/fuzzy-name-search/scripts/search_stock_cusip.py \
  --keywords '<company name>' \
  --quarter <quarter> \
  --topk 10
```

2) Rank top holders by VALUE:

```bash
python3 /skills/13f-analyzer/scripts/holding_analysis.py \
  --cusip <cusip> \
  --quarter <quarter> \
  --topk 10 \
  --equity_only
```

This prints manager names alongside accession numbers.
