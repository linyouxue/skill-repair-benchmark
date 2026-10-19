# Dual 4 price conversion with sign + unit consistency

Use this when extracting energy LMPs or reserve MCPs from optimization dual values.

## Core idea

A dual value has units of **objective-units per constraint-unit**. To report $/MWh, you must ensure the priced constraint is expressed in MW (or correctly rescale from per-unit using `baseMVA`) and that you apply the correct sign convention for your constraint direction.

## Step-by-step

1. **Write the exact constraint you priced**, as implemented in code.
2. **Annotate units** on each term (MW or pu).
3. **Map the dual to the reported price**:
   - equality `g(x) == 0`: a small change in RHS has marginal value equal to the dual; sign depends on how you moved terms.
   - inequality `h(x) >= 0` (or `<= 0`): dual is nonnegative in most solvers; the reported price usually matches the marginal cost of tightening/relaxing that bound.
4. **Rescale** if the constraint is in per-unit: dividing by `baseMVA` converts $/pu to $/MW.

```python
import numpy as np

def price_from_dual(dual_val, *, in_pu: bool, baseMVA: float, sign: float):
    """Return $/MW (=$/MWh for 1h) from a dual with explicit choices."""
    if dual_val is None:
        return 0.0
    scale = 1.0 / baseMVA if in_pu else 1.0
    return float(sign) * float(dual_val) * float(scale)

# Example usage (you decide these from your written constraint):
energy_price = price_from_dual(balance_dual, in_pu=True, baseMVA=baseMVA, sign=-1.0)
reserve_price = price_from_dual(reserve_dual, in_pu=False, baseMVA=baseMVA, sign=+1.0)

assert np.isfinite(energy_price)
```

## Runtime branch: wrong sign or magnitude

- **If prices are 1e3 larger than expected** (e.g., millions):
  - likely multiplied by `baseMVA` when you should divide (or vice versa) → re-check whether the balance was in MW or pu.
- **If signs are flipped** (e.g., mostly negative when marginal costs are positive):
  - likely moved terms across the equality or used `>=` vs `<=` in the opposite direction → re-derive sign using a 1-bus test (below).

## Verification: marginal-cost consistency check

At an uncongested solution with a price-setting generator not at bounds:
- energy LMP at that generator bus should approximately equal the generator marginal cost
- reserve MCP should be near the marginal reserve offer (or near zero if reserve is slack)

```python
# After solve:
P = float(Pg_MW[i])
mc = 2*c2*P + c1  # $/MWh

if (P > pmin_MW[i] + 1e-3) and (P < pmax_MW[i] - 1e-3):
    if abs(lmp_bus - mc) > 5.0:
        raise AssertionError("LMP not consistent with marginal cost; re-check dual sign/units")
```

Corrective action on failure: go back to step 1 and rewrite the priced constraint in MW with an explicit RHS so the dual interpretation is unambiguous, then recompute prices.
