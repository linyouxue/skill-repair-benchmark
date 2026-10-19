# Reserve offers and priced reserve co-optimization

Use this when the task expects a nonzero reserve MCP or otherwise implies reserves are *priced* (co-optimized energy + reserve procurement) rather than *free* feasibility headroom.

## 1) Data audit: find reserve offer fields and interpret units

Typical patterns:
- **Per-generator reserve offer**: `reserve_offer`, `reserve_price`, `offer_reserve`, etc. ($/MW or $/MWh)
- **Piecewise reserve offer curve**: breakpoints + costs, similar to MATPOWER type-1 gencost
- **Implicit reserve price adder**: a uniform penalty for reserve shortfall (then MCP is that penalty when binding)

```python
import json
from collections.abc import Mapping

with open("network.json") as f:
    data = json.load(f)

# Heuristic search for candidate keys (keeps you from assuming none exist)
needle = ("reserve", "spin", "reg")
keys = [k for k in data.keys() if any(n in k.lower() for n in needle)]
print("top-level reserve-ish keys:", keys)

column_info = data.get("column_info", {})
if isinstance(column_info, Mapping):
    for k in keys:
        if k in column_info:
            print("metadata", k, ":", column_info[k])
```

Runtime branch:
- **If you find a per-generator price vector** (length = n_gen), treat it as marginal $/MWh and model reserve cost as linear in `Rg`.
- **If you find curve/breakpoint data**, convert it to a convex piecewise-linear cost (epigraph) and add to the objective.
- **If you find no reserve offer data**, stop: priced reserve MCP is not identified from feasibility constraints alone; either treat reserve as free (MCP≈0) or use an explicit shortfall penalty if the task defines one.

## 2) Modeling branch A: linear reserve offers

```python
import cvxpy as cp
import numpy as np

Rg = cp.Variable(n_gen)
reserve_offer = np.asarray(reserve_offer_dollars_per_MWh, dtype=float)

constraints = [Rg >= 0, Rg <= reserve_capacity_MW]
constraints += [Pg_MW + Rg <= pmax_MW]
reserve_con = cp.sum(Rg) >= reserve_requirement_MW
constraints.append(reserve_con)

reserve_cost = cp.sum(cp.multiply(reserve_offer, Rg))
objective = cp.Minimize(energy_cost + reserve_cost)
```

## 3) Modeling branch B: piecewise-linear reserve offers (convex epigraph)

Assume each generator has breakpoints `(q_k, c_k)` with nondecreasing slopes.

```python
import cvxpy as cp

Rg = cp.Variable(n_gen)
reserve_cost_terms = []

for i in range(n_gen):
    # q: quantities (MW), c: total cost at each breakpoint ($/h)
    q = reserve_q_breakpoints[i]
    c = reserve_c_breakpoints[i]

    t = cp.Variable()  # epigraph variable for cost of i
    reserve_cost_terms.append(t)

    # t >= affine interpolants across each segment
    for k in range(len(q) - 1):
        slope = (c[k+1] - c[k]) / (q[k+1] - q[k])
        t >= c[k] + slope * (Rg[i] - q[k])

constraints += [Rg[i] >= q[0], Rg[i] <= q[-1]]

reserve_cost = cp.sum(reserve_cost_terms)
objective = cp.Minimize(energy_cost + reserve_cost)
```

## 4) Price extraction + verification

After solving, you can report a reserve MCP from the reserve requirement constraint dual **only after** ensuring units/sign match the written constraint.

```python
reserve_mcp = -float(reserve_con.dual_value)  # if written as sum(Rg) >= req (MW)

# Verification 1: binding check
binding = (cp.sum(Rg).value is not None) and (cp.sum(Rg).value <= reserve_requirement_MW + 1e-6)

# Verification 2: marginal offer consistency (linear offers)
if binding:
    awarded = (Rg.value > 1e-6)
    if awarded.any():
        mc = float(reserve_offer[awarded].max())
        assert abs(reserve_mcp - mc) < 1e-2 * max(1.0, abs(mc)), "reserve MCP not consistent with marginal awarded offer"
```

Next corrective action on failure:
- If `binding` is false but the task expects scarcity pricing, re-check the reserve requirement value/units and whether the constraint direction is correct.
- If the marginal consistency assertion fails, re-derive the reserve MCP sign/scale from the exact constraint algebra (and confirm `Rg`/requirement are in MW), then re-solve and re-check.
