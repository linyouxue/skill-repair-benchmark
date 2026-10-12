# Spec-literal predicates for conditional UI behavior (D3)

## Trigger
Read this when the spec defines a conditional rule via **missingness**, **thresholds**, or a **composite predicate** (e.g., “do not show tooltip when fields F are absent”) and you are tempted to replace it with a label/proxy (e.g., `type === 'ETF'`).

## Why this fails
Autograders often check the *literal condition* (or include hidden rows) rather than the dataset’s current “obvious” labels. A proxy can pass a quick eyeball test but fail rubric checks when:
- labels differ by case/whitespace/alternate spelling
- non-category rows also have missing fields
- the spec’s predicate is intentionally data-driven (missingness) rather than semantic (label)

## Procedure

1. **Copy the spec predicate into code comments** near the handler it gates.
2. Implement it as a **named pure function** (e.g., `suppressTooltip(d)`), not inline in the event handler.
3. **Keep proxies separate**: you may still compute `categoryForColor(d)` for legends/colors, but it must not replace the spec predicate.
4. Choose verification rows by the predicate itself (one that returns `true`, one that returns `false`).

## Runnable Python: find one example on each side of the predicate

```python
import csv

def is_missing(v):
    return v is None or str(v).strip() == ""

path = "data.csv"  # replace
fields = ["a", "b", "c"]  # replace with fields named in the spec

true_row = false_row = None
with open(path, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        pred = all(is_missing(row.get(k)) for k in fields)
        if pred and true_row is None:
            true_row = row
        if (not pred) and false_row is None:
            false_row = row
        if true_row and false_row:
            break

print("predicate-true example:", {k: true_row.get(k) for k in fields} if true_row else None)
print("predicate-false example:", {k: false_row.get(k) for k in fields} if false_row else None)
```

## Runtime branch

- **If** you cannot find a `predicate-true` row in the data:
  - the spec predicate may be wrong/misread, or the dataset differs; re-read the spec and inspect the CSV columns.
- **If** you cannot find a `predicate-false` row:
  - your predicate is too broad; tighten it (e.g., `anyMissing` vs `allMissing`) to match the spec wording.

## Verification (and corrective action on failure)

1. In the rendered page, hover the `predicate-true` example:
   - confirm the suppressed behavior occurs (e.g., tooltip stays hidden).
2. Hover the `predicate-false` example:
   - confirm the normal behavior occurs (e.g., tooltip appears with required fields).

**If either check fails:**
- rewrite the predicate function to match the spec wording (`all` vs `any`, trimming, numeric parsing),
- ensure the hover handler uses the predicate directly,
- then re-run the same two hovers.
