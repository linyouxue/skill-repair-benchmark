# Ambiguity handling and flagging for mixed-unit labs

Use this procedure when range-triggered conversion yields **multiple in-range candidates** (or none), especially for analytes whose unit systems have **overlapping plausible ranges**.

## Goal

Prevent silent scale shifts by recording *what you did* (kept/converted/ambiguous) and producing an audit trail that supports review.

## Procedure (runnable Python)

```python
import pandas as pd
import numpy as np

def harmonize_with_audit(df, numeric_cols, ref_ranges, ref_conversions, tol=0.0):
    """Return (harmonized_df, audit_df) with explicit ambiguity handling."""

    def in_range(x, lo, hi):
        return (lo - tol) <= x <= (hi + tol)

    audit_rows = []
    out = df.copy()

    for col in numeric_cols:
        if col not in ref_ranges:
            out[col] = out[col]
            continue

        lo, hi = ref_ranges[col]
        factors = ref_conversions.get(col, [])

        new_vals = []
        statuses = []

        for i, v in enumerate(out[col].values):
            if pd.isna(v):
                new_vals.append(v)
                statuses.append('missing')
                continue

            if in_range(v, lo, hi):
                new_vals.append(v)
                statuses.append('kept_in_range')
                continue

            hits = []
            for f in factors:
                cand = v * f
                if in_range(cand, lo, hi):
                    hits.append((f, cand))

            if len(hits) == 1:
                f, cand = hits[0]
                new_vals.append(cand)
                statuses.append('converted')
                audit_rows.append({
                    'row': i,
                    'feature': col,
                    'original': float(v),
                    'action': 'converted',
                    'factor': float(f),
                    'converted': float(cand),
                })
            elif len(hits) >= 2:
                # Branch A: ambiguous -> do not force
                new_vals.append(v)
                statuses.append('ambiguous_multi_hit')
                audit_rows.append({
                    'row': i,
                    'feature': col,
                    'original': float(v),
                    'action': 'kept_ambiguous_multi_hit',
                    'factor': None,
                    'converted': None,
                    'candidates': [(float(f), float(c)) for f, c in hits],
                })
            else:
                # Branch B: no match -> do not force
                new_vals.append(v)
                statuses.append('no_in_range_candidate')
                audit_rows.append({
                    'row': i,
                    'feature': col,
                    'original': float(v),
                    'action': 'kept_no_in_range_candidate',
                    'factor': None,
                    'converted': None,
                })

        out[col] = new_vals
        out[col + '_status'] = statuses

    audit = pd.DataFrame(audit_rows)
    return out, audit
```

## Runtime branch guidance

- If `*_status == 'ambiguous_multi_hit'`: treat the feature as mixed/uncertain for that row; do not apply blanket feature-level conversions.
- If `*_status == 'no_in_range_candidate'`: treat as data-quality anomaly; consider leaving unchanged and escalating to domain review or expanding the reference conversion list.

## Verification

After harmonization, compute checks that can fail loudly.

```python

def verify_harmonization(df, numeric_cols, ref_ranges, max_ambiguous_rate=0.01):
    """Return (ok, report). If not ok, prescribes next corrective action."""
    report = {}

    # 1) In-range rate check (ignoring missing)
    for col in numeric_cols:
        if col not in ref_ranges or col not in df:
            continue
        lo, hi = ref_ranges[col]
        s = pd.to_numeric(df[col], errors='coerce')
        non_missing = s.notna().sum()
        if non_missing == 0:
            continue
        out_of_range = ((s < lo) | (s > hi)).sum()
        report[col] = {
            'non_missing': int(non_missing),
            'out_of_range': int(out_of_range),
        }

    # 2) Ambiguity rate check
    status_cols = [c for c in df.columns if c.endswith('_status')]
    ambiguous = 0
    total = 0
    for sc in status_cols:
        total += df[sc].notna().sum()
        ambiguous += (df[sc] == 'ambiguous_multi_hit').sum()
    amb_rate = (ambiguous / total) if total else 0.0

    ok = (amb_rate <= max_ambiguous_rate)
    report['ambiguous_rate'] = float(amb_rate)

    if not ok:
        report['next_action'] = (
            "Too many ambiguous conversions. Do NOT add unconditional heuristics; "
            "instead: (a) tighten/verify per-feature min/max reference ranges, "
            "(b) confirm conversion candidate list for those features, "
            "(c) if still ambiguous, keep values unchanged and route to manual review." 
        )

    return ok, report
```

If verification fails, follow `next_action` and re-run `harmonize_with_audit()` after updating the **reference** (ranges/conversion candidates), not by adding always-convert heuristics.
