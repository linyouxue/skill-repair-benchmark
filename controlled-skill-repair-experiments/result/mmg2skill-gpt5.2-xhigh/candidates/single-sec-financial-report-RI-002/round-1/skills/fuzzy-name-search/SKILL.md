---
name: fuzzy-name-search
description: This skill includes search capability in 13F, such as fuzzy search a fund information using possibly inaccurate name, or fuzzy search a stock cusip info using its name.
---

## Overview

This tool is essentially a search engine that provides you the ability to search a fund or stock meta information with a name. Note that you don't have to provide the accurate name since this tool has built-in fuzzy string search algorithms based on Levinsteins.

The search helpers are installed under `/skills/fuzzy-name-search/scripts`,
while filing data lives under `/root/<quarter>`. Run the helpers from their
absolute `/skills/...` paths; do not look for them under `/root/scripts` or
replace them merely because the current working directory is `/root`.

## Usage

### Fuzzy search a fund using its name

```bash
python3 /skills/fuzzy-name-search/scripts/search_fund.py --keywords "bridgewater" --quarter 2025-q2 --topk 10
```

If the expected filer is not present in the top-k fuzzy results, fall back to a
direct substring scan of that quarter’s `COVERPAGE.tsv`, then validate the
chosen accession number with exact search:

```bash
python3 - <<'PY'
import pandas as pd

quarter = "2025-q3"
kw = "renaissance technologies"

cp = pd.read_csv(f"/root/{quarter}/COVERPAGE.tsv", sep="\t", dtype=str)
m = cp[cp["FILINGMANAGER_NAME"].str.contains(kw, case=False, na=False)]
m = m[m["ISAMENDMENT"] == "N"][["ACCESSION_NUMBER","FILINGMANAGER_NAME","REPORTCALENDARORQUARTER"]]
print(m.head(20).to_string(index=False))
PY
```

Then confirm the exact record:

```bash
python3 /skills/fuzzy-name-search/scripts/search_fund.py \
    --accession_number 0000000000-00-000000 \
    --quarter 2025-q3
```

Normalize whitespace and case when reviewing matches. Verify the returned
manager name and prefer a non-amendment filing. Accession numbers are filing
identifiers, so search and validate them independently for every quarter; never
reuse one quarter's accession number for another quarter.

### Exact search a fund using accession number

```bash
python3 /skills/fuzzy-name-search/scripts/search_fund.py \
    --accession_number 0001172661-25-003151 \
    --quarter 2025-q2
```

### Fuzzy search a stock using its name

```bash
python3 /skills/fuzzy-name-search/scripts/search_stock_cusip.py \
    --keywords palantir \
    --topk 10
```

Normalize CUSIPs to uppercase and confirm the selected CUSIP occurs in the
requested quarter's `INFOTABLE`. If a name maps to common equity and option
positions, a request for the stock means the non-option common-equity CUSIP;
do not substitute a Call or Put position.
