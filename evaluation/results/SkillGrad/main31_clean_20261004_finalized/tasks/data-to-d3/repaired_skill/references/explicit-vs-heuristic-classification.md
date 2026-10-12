# Explicit label vs heuristic classification (D3 data rules)

## Trigger
Read this when you are about to implement conditional behavior by inferring a category from **missing values**, **ranges**, or other proxies.

## Rule of thumb
If the dataset (or spec) provides an **explicit label/flag**, use it for category membership. Treat missingness as an independent concern (fallback display), not as evidence of membership.

Read references/spec-literal-predicates.md when the spec defines membership/behavior *via missingness* (i.e., missingness is the explicit rule, not a proxy). Skip when you only need to decide whether to trust an explicit label.

## Runnable Python: detect proxy-risk rows

```python
import csv
from collections import Counter

path = "data.csv"  # replace
label_field = "category"  # replace
proxy_field = "value"      # replace

counts = Counter()
proxy_missing_by_label = Counter()

with open(path, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        label = (row.get(label_field) or "").strip()
        proxy_missing = (row.get(proxy_field) in (None, ""))
        counts[label] += 1
        if proxy_missing:
            proxy_missing_by_label[label] += 1

print("rows by label:", counts)
print("proxy-missing by label:", proxy_missing_by_label)

# Branch: risk signal
risk = any(lbl != "" and proxy_missing_by_label[lbl] > 0 for lbl in counts)
print("proxy classification risk:", risk)
```

## Runtime branch

- **If** `risk` is true: do *not* use proxy missingness as category membership; implement `isCategory = (label == 'X')` and handle missing proxy values with fallback rendering.
- **Else**: proxy classification may be acceptable *only if the spec defines it*.

## Verification (and corrective action on failure)

1. Pick one row where the explicit label is non-X but the proxy field is missing.
2. Confirm it still receives the non-X behavior (e.g., tooltip shown, non-uniform sizing).

**If it fails:** split the logic into two functions:
- `isX(d)` based on explicit label/flag
- `valueForScale(d)` with fallback for missing values
Then re-run the check on the same row.
