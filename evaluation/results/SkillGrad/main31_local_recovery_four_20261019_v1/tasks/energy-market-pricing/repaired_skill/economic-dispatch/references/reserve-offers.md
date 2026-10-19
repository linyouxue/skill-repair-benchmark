# Reserve offers/costs in co-optimization

Read this when the task expects a nonzero reserve MCP or provides reserve offer data in an unclear format.

## 1) Identify the reserve price signal in the data

Runtime branch: reserve offers may be explicit, implicit via piecewise costs, or absent.

```python
def detect_reserve_offer_format(data):
    keys = set(data.keys())
    if "reserve_offer" in keys:
        return "linear_offer"
    if "reserve_gencost" in keys:
        return "matpower_like"
    if "reserve_shortfall_penalty" in keys:
        return "penalty_only"
    return "absent"
```

## 2) Build the reserve term (generic templates)

```python
import cvxpy as cp

Rg = cp.Variable(n_gen, nonneg=True)

# Requirement (system-wide template)
reserve_con = cp.sum(Rg) >= reserve_requirement

fmt = detect_reserve_offer_format(data)

if fmt == "linear_offer":
    offer = data["reserve_offer"]  # $/MWh, per generator
    reserve_cost = cp.sum(cp.multiply(offer, Rg))

elif fmt == "penalty_only":
    # Introduce a shortfall variable with a scarcity penalty.
    shortfall = cp.Variable(nonneg=True)
    constraints = [reserve_con + shortfall >= reserve_requirement]
    penalty = float(data["reserve_shortfall_penalty"])
    reserve_cost = penalty * shortfall

elif fmt == "matpower_like":
    # Treat reserve as another product with its own cost curve.
    # Keep as a placeholder: parse with the same gencost machinery used for energy.
    reserve_cost = cp.sum(cp.multiply(reserve_offer_prices, Rg))

else:  # absent
    reserve_cost = 0.0
```

## 3) What to report as “reserve MCP”

Runtime branch: only priced reserves yield an interpretable market-clearing reserve MCP.

```python
priced = fmt in {"linear_offer", "penalty_only", "matpower_like"}

if priced:
    reserve_mcp = -float(reserve_con.dual_value)  # sign depends on how you wrote the constraint
else:
    reserve_mcp = None
```

## Verification step (must prescribe corrective action)

1. If `priced` is **False** but the task requires a reserve MCP: revisit the input parsing to find reserve offer or shortfall penalty fields; if none exist, report that MCP is undefined under free reserves and do not output a numeric “market” MCP.
2. If `priced` is **True** and `reserve_mcp` is ~0 while the requirement is binding:
   - check the constraint direction/sign and unit system,
   - verify the objective actually includes `reserve_cost`,
   - if still ~0, inspect whether the marginal awarded reserve offer has ~0 cost (data issue) or whether degeneracy makes duals unstable (try another solver).
