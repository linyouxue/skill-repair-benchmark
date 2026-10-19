---
name: lab-unit-harmonization
description: Harmonize clinical lab values by parsing messy numerics, converting mixed unit systems into a single target, and validating outputs against authoritative feature ranges.
---

# Lab Unit Harmonization

## Core Workflow

1. **Parse first, convert second**: normalize raw strings (scientific notation, decimal separators, whitespace) into floats before any unit logic.
2. **Anchor to the reference**: for each feature, treat the reference dictionary as the source of truth for (a) *target output unit* and (b) *valid min/max range in that unit*.
3. **Use ranges as unit evidence (not as the gate)**: pick conversion factors at the *feature* level by distribution fit; avoid per-value “try conversions until it fits” and avoid “already in range ⇒ correct unit” when ranges can overlap.
4. **Keep reference ranges fixed**: treat the authoritative `(lo, hi)` as immutable; if many values are out-of-range or typicals don’t match, adjust conversion candidates (including trying inverse factors) or quarantine/flag, but do not broaden/shift the range to make values pass.
5. **Verify post-write**: run (a) a range re-check against the same authoritative ranges and (b) a unit-sanity audit using summary stats/typical values for the *target unit* (median/quantiles), not only broad min/max.

## Parse Numeric Formats

Normalize heterogeneous numeric strings into floats.

```python
import numpy as np

def parse_float(x):
    if x is None:
        return np.nan
    s = str(x).strip()
    if s == '' or s.lower() in {'nan', 'none', 'null'}:
        return np.nan
    # decimal comma (when used as decimal separator)
    if ',' in s and '.' not in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return np.nan
```

## Unit Conversion (Feature-Level Fit)

Convert values into the *target unit* by scoring candidate conversion factors against the authoritative target-unit range.

```python
import numpy as np

def pct_out_of_range(xs, lo, hi, tol=0.0):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and np.isnan(x))]
    if not xs:
        return 0.0
    return sum((x < lo - tol) or (x > hi + tol) for x in xs) / len(xs)

def convert_with_best_factor(values, target_range, candidate_factors, tol=0.0):
    lo, hi = target_range
    best = (pct_out_of_range(values, lo, hi, tol=tol), None)
    for f in candidate_factors:
        ys = [v * f if v is not None and not (isinstance(v, float) and np.isnan(v)) else v for v in values]
        cand = (pct_out_of_range(ys, lo, hi, tol=tol), f)
        if cand[0] < best[0]:
            best = cand
    return best  # (pct_out, factor or None)
```

Decision rule: tolerance is only for float noise near boundaries; never use tolerance, per-value factor selection, or range-widening to make clearly wrong-unit values appear valid.

Read references/range_unit_consistency_guardrail.md when a feature’s `% out of range` is low but the *distribution/typicals* suggest a different unit regime (or when you feel tempted to broaden/shift `(lo, hi)` or to accept the first factor that makes a value “fit”). Skip when the target unit is unambiguous and range fit plus typicals both agree.

## Format Output (Stable Precision)

Emit consistent string formatting after all numeric transformations, then validate formatting constraints **per cell** (not by scanning the serialized CSV text).

```python
import re

_DECIMAL_DOT_2DP = re.compile(r"^-?\d+\.\d{2}$")

def format_fixed(x, decimals=2):
    return '' if x is None else f"{x:.{decimals}f}"

def validate_cells_are_dot_decimal(series_as_str, pattern=_DECIMAL_DOT_2DP):
    bad = [s for s in series_as_str if s != '' and not pattern.match(s)]
    assert not bad, f"bad formatted cells: {bad[:5]}"
```

Decision rule: treat “no commas” / “dot decimal” requirements as constraints on **field values**; never regex the whole CSV text for commas because delimiter commas guarantee matches.

## Common Pitfalls

- **Using broad ranges as the definition of the target unit**: a permissive `(lo, hi)` can make the wrong unit look “in range,” or can drift the target unit entirely; anchor target unit + range in an authoritative feature dictionary, then validate typicals.
- **Per-value “try conversions until it fits”**: choosing factors per cell can silently misconvert bimodal/unit-mixed features; pick a feature-level factor (or explicitly branch/quarantine) based on distribution fit.
- **One-direction conversion only**: some unit confusions require trying both multiply and divide (i.e., include inverse factors) to find the best fit.
- **Converting before parsing**: unit conversion on unparsed strings (scientific notation, decimal comma) can create false outliers and bad conversions.
- **CSV-level regex checks for per-cell formatting**: scanning the whole file for patterns like `\d,\d` confuses separators with decimal commas; validate per field (and reload with `dtype=str` if checking post-write).
- **Over-tolerance or clamping**: tolerance is for boundary float noise, not for rescuing clearly invalid values.
