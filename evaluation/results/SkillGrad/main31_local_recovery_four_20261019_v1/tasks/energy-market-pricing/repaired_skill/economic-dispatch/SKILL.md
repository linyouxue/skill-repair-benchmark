---
name: economic-dispatch
description: "Economic dispatch and reserve co-optimization using consistent units, generator limits, and cost functions."
---

# Economic Dispatch

Economic dispatch minimizes total generation cost while meeting load demand and respecting generator and (optionally) reserve requirements.

## Artifact capture audit (workflow)

Before finalizing, ensure required deliverables are written to a grader-captured location and are externally visible.

1. Write artifacts to the task workspace (avoid virtualenv/system directories).
2. Confirm location and presence (`pwd`, `ls -la`).
3. Print a small preview and checksum to prove the file is real.

```python
from pathlib import Path
import hashlib

p = Path("output.json")
assert p.exists() and p.is_file()
blob = p.read_bytes()
print(blob[:200])
print(hashlib.sha256(blob).hexdigest())
```

Decision rule: if the required file is missing from the visible output inventory, rewrite it into the workspace root and re-run the audit.

## Unit consistency (MW vs per-unit)

If you model `Pg` in per-unit but other quantities (limits, reserves) in MW, explicitly convert and keep each constraint internally consistent.

```python
import cvxpy as cp

Pg = cp.Variable(n_gen)      # per-unit
Rg = cp.Variable(n_gen)      # MW (example)

Pg_MW = Pg * baseMVA

constraints = [Rg >= 0]
constraints += [Pg_MW >= pmin_MW, Pg_MW <= pmax_MW]
```

Decision rule: if any constraint mixes MW and per-unit on the same side, fix units before solving.

## Reserve co-optimization (priced vs free)

Reserve requirements alone do not define a priced reserve market. Before you compute a reserve MCP from duals, determine whether the input provides **reserve offers/costs** and whether the task expects priced reserves.

```python
import cvxpy as cp

# Rg in MW after unit audit/conversion.
Rg = cp.Variable(n_gen)

reserve_con = cp.sum(Rg) >= reserve_requirement
constraints.append(reserve_con)

# Template: add reserve procurement cost only when you have reserve offers.
reserve_offer = reserve_offer_dollars_per_MWh  # vector, from input
reserve_cost = cp.sum(cp.multiply(reserve_offer, Rg))

objective = cp.Minimize(energy_cost + reserve_cost)
```

Decision rule:
- If reserve offer/cost data exists (or a shortfall penalty defines scarcity cost), include the reserve cost term in the objective and include it in `total_cost_dollars_per_hour`; then a binding reserve constraint should yield a reserve MCP consistent with the marginal awarded reserve offer (or penalty).
- If no reserve offer/cost data exists, explicitly treat reserve as free (objective excludes reserve cost) and do not claim a benchmark-matching “market-clearing reserve MCP”; at most, report it as a shadow price under a free-reserve assumption.

Read references/reserve-offers.md when the task expects a nonzero reserve MCP or the reserve offer format is unclear.
Skip when reserves are not modeled.

## Cost function format

MATPOWER gencost polynomial (model=2) uses coefficients on **MW**.

```python
cost = 0
for i in range(n_gen):
    Pg_MW_i = Pg_MW[i]
    ncost = int(gencost[i, 3])
    coeffs = gencost[i, 4:4+ncost]

    if ncost == 3:
        c2, c1, c0 = coeffs
        cost += c2 * cp.square(Pg_MW_i) + c1 * Pg_MW_i + c0
    elif ncost == 2:
        c1, c0 = coeffs
        cost += c1 * Pg_MW_i + c0
```

Read references/cost-functions.md when gencost includes piecewise-linear type-1 or variable NCOST.
Skip when all costs are quadratic with NCOST=3.

## Common pitfalls

- Building reserve constraints without first confirming whether reserve fields are MW vs per-unit (can yield feasible but semantically wrong prices/dispatch).
- Mixing MW and per-unit within the same constraint, then “fixing” results by rescaling duals instead of fixing the model units.
- Adding a reserve requirement constraint but omitting reserve procurement cost (or a defined shortfall penalty) while still attempting to report a market-clearing reserve MCP from duals.