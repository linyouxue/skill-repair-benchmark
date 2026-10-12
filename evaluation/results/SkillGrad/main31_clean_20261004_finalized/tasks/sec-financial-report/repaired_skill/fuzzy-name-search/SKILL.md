---
name: fuzzy-name-search
description: Find canonical 13F fund accessions and stock CUSIPs using repository search scripts, then defer metric computation to analysis scripts.
---

## Overview

Use this skill to resolve **identifiers** (fund accession numbers and stock CUSIPs). For any numeric outputs (AUM, holdings counts, deltas, top holders), switch to the analysis scripts that encode benchmark semantics.

## Workflow

1. Verify the repository scripts exist (`scripts/search_fund.py`, `scripts/search_stock_cusip.py`) before attempting any custom fuzzy matching.
2. If scripts are not found immediately, confirm you are at the repo/workspace root, then search from *your current directory* (not a guessed path) and verify the files exist before continuing.
3. Run the appropriate search script and capture the canonical identifier (accession number or CUSIP) from its output.
4. Hand off to `scripts/one_fund_analysis.py` or `scripts/holding_analysis.py` for all metric computations.

Read references/13f-script-first.md when `scripts/*.py` is not found where you first looked or you feel tempted to implement bespoke fuzzy matching. Skip when the task provides a canonical accession/CUSIP already.

## Usage

### Fuzzy search a fund using its name

```bash
python3 scripts/search_fund.py --keywords "<fund keywords>" --quarter <quarter> --topk <k>
```

### Lookup a fund by accession number

```bash
python3 scripts/search_fund.py \
  --accession_number <accession> \
  --quarter <quarter>
```

### Fuzzy search a stock using its name

```bash
python3 scripts/search_stock_cusip.py \
  --keywords "<stock keywords>" \
  --topk <k>
```

## Common Pitfalls

- Treating search output as sufficient to compute metrics; search scripts only resolve identifiers.
- Replacing provided search scripts with ad-hoc fuzzy matching, which can pick the wrong entity/accession/CUSIP.
