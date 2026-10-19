# Range/unit consistency guardrail (prevent “making data pass”)

Use this procedure when unit inference via range fit is producing wrong-unit outputs (including the subtle case where values are *in range* but still in the wrong unit) and you find yourself wanting to broaden/shift the acceptable min/max.

## Goal

Keep *output unit*, *validation range*, and *conversion factors* internally consistent by anchoring to an authoritative feature dictionary and adding a post-conversion unit-sanity audit.

## Procedure (with runtime branches)

```python
import numpy as np

def summarize(xs):
    xs = np.asarray([x for x in xs if x is not None and not (isinstance(x, float) and np.isnan(x))])
    if xs.size == 0:
        return {"n": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None}
    q25, q50, q75 = np.quantile(xs, [0.25, 0.5, 0.75])
    return {
        "n": int(xs.size),
        "min": float(xs.min()),
        "p25": float(q25),
        "median": float(q50),
        "p75": float(q75),
        "max": float(xs.max()),
    }

def summarize_out_of_range(xs, lo, hi):
    xs = np.asarray([x for x in xs if x is not None and not (isinstance(x, float) and np.isnan(x))])
    if xs.size == 0:
        return {"n": 0, "pct_out": 0.0, "min": None, "max": None}
    out = (xs < lo) | (xs > hi)
    return {
        "n": int(xs.size),
        "pct_out": float(out.mean()),
        "min": float(xs.min()),
        "max": float(xs.max()),
    }

def choose_conversion_by_fit(values, target_range, candidate_factors, tol=0.0):
    lo, hi = target_range
    base = summarize_out_of_range(values, lo, hi)

    # Branch A: already mostly in range → do not immediately assume correct unit
    # (range overlap/permissive ranges exist); fall through to optional audit.
    if base["n"] > 0 and base["pct_out"] <= 0.05:
        return {"action": "audit_first", "factor": None, "diagnostic": base}

    # Branch B: try factors; pick the one that yields best in-range fit
    best = (base["pct_out"], None, base)
    for f in candidate_factors:
        converted = [v * f if v is not None and not (isinstance(v, float) and np.isnan(v)) else v for v in values]
        summ = summarize_out_of_range(converted, lo - tol, hi + tol)
        cand = (summ["pct_out"], f, summ)
        if cand[0] < best[0]:
            best = cand

    pct_out, factor, summ = best
    if factor is None:
        return {"action": "no_good_factor", "factor": None, "diagnostic": summ}
    return {"action": "convert", "factor": factor, "diagnostic": summ}

def unit_sanity_audit(values_in_target_unit, typical_range):
    """typical_range is a tighter 'typical' band for the target unit (not min/max)."""
    lo_t, hi_t = typical_range
    s = summarize(values_in_target_unit)
    if s["n"] == 0:
        return {"ok": True, "reason": "empty", "summary": s}
    # simple heuristic: median should land in a typical band
    ok = (lo_t <= s["median"] <= hi_t)
    return {"ok": bool(ok), "reason": "median_in_typical" if ok else "median_outside_typical", "summary": s}
```

### How to use it

1. For a single feature, collect its parsed numeric values.
2. Look up the **target output unit** and the **target-unit min/max range** `(lo, hi)` from the authoritative reference for that feature.
3. Provide plausible `candidate_factors` (include inverses when direction is uncertain).
4. Run `choose_conversion_by_fit`.

### Runtime branches

- If `action == "convert"`: apply `factor` and proceed to verification.
- If `action == "audit_first"`: do a unit-sanity audit using a **tighter unit-specific typical range** (median/quantiles), then:
  - If audit passes, keep values as-is.
  - If audit fails, **force trying conversions anyway** (treat as an overlap/ambiguous-unit case) and re-run `choose_conversion_by_fit` on the same candidate factors; if still ambiguous, flag/quarantine.
- If `action == "no_good_factor"`: do not change `(lo, hi)`; expand candidate factors (including inverse), re-check parsing, or quarantine.

## Verification (and corrective action on failure)

After applying the chosen action/factor:

1. Verify: recompute `% out of range` against the **same** authoritative `(lo, hi)`.
2. Verify: run `unit_sanity_audit` against a tighter typical range for the target unit.

If either verification fails:

- **Do not change `(lo, hi)`**.
- Add/adjust conversion candidates (missing inverse? wrong direction? alternate conventional units?).
- Re-check parsing (decimal comma / scientific notation) and missing/sentinel handling.
- If still unresolved, quarantine the feature (flag it) rather than emitting values that claim the target unit.

## Common failure mode this prevents

If observed values cluster in a plausible range for a *different unit* and you “fix” it by redefining the target range (or by skipping conversion because values are “in range”), you can produce an internally inconsistent dataset: the column is claimed to be in the target unit system, but the numeric magnitudes remain in the source unit system.
