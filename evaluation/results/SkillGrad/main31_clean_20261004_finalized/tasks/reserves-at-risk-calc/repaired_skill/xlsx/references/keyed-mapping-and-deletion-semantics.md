# Keyed mapping + deletion semantics (preserve order/alignment)

Use this when the workbook requires you to (1) build a key list from observed data (e.g., countries/series in a wide table), then (2) apply a later step that says to **delete/exclude** keys with missing data, while downstream formulas assume positional alignment across rows/blocks.

Typical symptoms of failure:
- wildcard header matching (e.g., `"*"&key&"*"`) pulls the wrong column when multiple headers contain similar text
- “deletion” implemented by writing a shorter list and blanking the remainder, which changes which key is in each position relative to expected downstream columns

## Procedure

### 1) Define stable keys from headers (not fuzzy parsing)
Prefer a stable tokenization rule that matches the workbook’s header convention.

- If headers look like `Key: Series Name`, define `key = TEXTBEFORE(header, ":")`.
- If headers are already just keys, use exact header text.

### 2) Match columns by exact key/prefix (avoid wildcards)
In Excel, find the column for each key using an exact match on either:
- the full header (best), or
- a consistent prefix pattern like `key & ":"` when the suffix varies but the delimiter is stable.

### 3) Implement “delete” as a gate on the *key cell* (not tail-blanking)
Start from the Step-2 key list/order. For each position, look up the required predicate (e.g., “total for target year exists”). Then gate the Step-3 key cell itself.

- If predicate is missing/blank/#N/A: Step-3 key cell becomes blank (excluded).
- Otherwise: Step-3 key cell equals Step-2 key.

Downstream Step-3 formulas should reference Step-3 keys (and/or wrap lookups in `IF(key="", "", <lookup>)`) so excluded keys do not propagate values.

## Runnable Python helper (to validate semantics offline)

This script doesn’t edit Excel; it validates that a Step-3 list equals “Step-2 list minus excluded keys, preserving order.”

```python
import re

def stable_key(header: str) -> str:
    header = (header or "").strip()
    # Branch: delimiter style
    if ":" in header:
        return header.split(":", 1)[0].strip()
    return re.sub(r"\s+", " ", header)

step2 = ["A", "B", "C", "D"]
# total_2025_present maps key -> bool predicate
total_2025_present = {"A": True, "B": False, "C": True, "D": True}

step3_expected = [k for k in step2 if total_2025_present.get(k, False)]

# Branch: produced list may include blanks (gated cells)
step3_produced = ["A", "", "C", "D"]
step3_compact = [k for k in step3_produced if k]

assert step3_compact == step3_expected, (step3_compact, step3_expected)
print("OK: Step 3 equals Step 2 minus excluded keys; order preserved")
```

## Verification (and corrective action)

1) **Key uniqueness check:** keys used for matching should be unique in the source headers.
- If duplicates exist (same key appears multiple times): refine the key definition to include a stable discriminator (e.g., `key + ":" + series_group`) before mapping.

2) **No-wildcard check:** ensure the mapping formulas do not use wildcard lookups as the primary match.
- If wildcards are present: replace with exact/prefix matching using `MATCH` on a constructed header prefix, or precompute a header helper row/column that contains stable keys.

3) **Deletion semantics check:** confirm Step-3 key row (after compacting blanks) equals `FILTER(step2_keys, total_2025_present)` while preserving order.
- If order differs or excluded keys still appear downstream: gate the Step-3 key cell with the predicate and wrap dependent formulas with `IF(key_cell="", "", ...)`, then recalc and re-check.
