# Unit audit for power-system optimization (MW vs per-unit)

Use this when inputs mix MATPOWER-style per-unit conventions with add-on fields (reserves, penalties, special limits).

## Checklist

1) Choose a primary unit system for the optimization (prefer **MW** if you must report prices/flows in $/MWh and MW).
2) Convert at ingest time and store converted arrays; avoid repeated conversions scattered across the model.
3) Add magnitude assertions to catch wrong-scale values early.

## Minimal runnable template

Runtime branch: infer unit scale from metadata when available; otherwise infer from magnitude.

```python
def infer_pu(values):
    vals = [abs(float(v)) for v in values if v is not None]
    if not vals:
        return False
    # Heuristic: per-unit powers are typically < 10, MW powers often > 10.
    return max(vals) < 10

baseMVA = float(baseMVA)

field_vals = raw_values
field_is_pu = metadata_says_pu if metadata_says_pu is not None else infer_pu(field_vals)

vals_MW = [float(v) * baseMVA for v in field_vals] if field_is_pu else [float(v) for v in field_vals]

# Verification assertions
assert all(abs(v) < 1e6 for v in vals_MW), "unrealistic MW magnitude; unit conversion likely wrong"
```

## Verification step (must prescribe corrective action)

- If magnitude assertions fail: print the metadata and sample raw values; then flip the `field_is_pu` decision and re-run the conversion.
- If later you observe inconsistent economics (e.g., LMPs off by ~baseMVA factor): re-check which constraints were written in pu vs MW and re-derive dual scaling from the written constraints.
