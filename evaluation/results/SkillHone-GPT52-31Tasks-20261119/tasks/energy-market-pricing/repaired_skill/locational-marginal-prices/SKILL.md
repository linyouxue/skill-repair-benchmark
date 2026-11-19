---
name: locational-marginal-prices
description: "Extract locational marginal prices (LMPs) from DC-OPF solutions using dual values. Use when computing nodal electricity prices, reserve clearing prices, or performing price impact analysis."
---

# Locational Marginal Prices (LMPs)

LMPs are the marginal cost of serving one additional MW of load at each bus. In optimization terms, they are the **dual values** (shadow prices) of the nodal power balance constraints.

## LMP Extraction from CVXPY

To extract LMPs, you must:
1. Store references to the balance constraints
2. Solve the problem
3. Read the dual values after solving

```python
import cvxpy as cp

# Store balance constraints separately for dual extraction
balance_constraints = []

for i in range(n_bus):
    pg_at_bus = sum(Pg[g] for g in range(n_gen) if gen_bus[g] == i)
    # Pd is fixed demand. Many MATPOWER cases also include shunt conductance Gs
    # (bus column 4) in MW at V=1.0 pu. In DC models (V≈1), treat it as
    # additional fixed real-power withdrawal.
    pd_pu = (buses[i, 2] + buses[i, 4]) / baseMVA

    # Write balance in per-unit as: gen_pu - load_pu == net_injection_pu
    balance_con = pg_at_bus - pd_pu == B[i, :] @ theta
    balance_constraints.append(balance_con)
    constraints.append(balance_con)

# Solve
prob = cp.Problem(cp.Minimize(cost), constraints)
prob.solve(solver=cp.CLARABEL)

# Extract LMPs from duals
lmp_by_bus = []
for i in range(n_bus):
    bus_num = int(buses[i, 0])
    dual_val = balance_constraints[i].dual_value  # units depend on balance scaling

    # IMPORTANT: CVXPY's sign convention for equality duals is such that for a
    # balance written as (gen_pu - load_pu == ...), the marginal energy price is
    #   LMP[$/MWh] = -dual / baseMVA
    # (If you formulate the balance in MW instead of pu, omit the /baseMVA.)
    lmp = (-float(dual_val) / baseMVA) if dual_val is not None else 0.0

    lmp_by_bus.append({
        "bus": bus_num,
        "lmp_dollars_per_MWh": round(lmp, 2)
    })
```

## LMP Sign Convention

For a balance constraint written as `generation - load == net_export`:

Note: If your extracted LMPs all appear to have the wrong sign, check the exact algebraic form of the balance constraint and your solver's dual sign convention. For the CVXPY form shown above, use `-dual/baseMVA`.
- **Positive LMP**: Increasing load at that bus increases total cost (typical case)
- **Negative LMP**: Increasing load at that bus *decreases* total cost

Negative LMPs commonly occur when:
- Cheap generation is trapped behind a congested line (can't export power)
- Adding load at that bus relieves congestion by consuming local excess generation
- The magnitude can be very large in heavily congested networks (thousands of $/MWh)

Negative LMPs are physically valid and expected in congested systems — they are not errors.

## Reserve Clearing Price

The reserve MCP is the dual of the system reserve requirement constraint:

```python
# Store reference to reserve constraint
reserve_con = cp.sum(Rg) >= reserve_requirement
constraints.append(reserve_con)

# After solving:
reserve_mcp = float(reserve_con.dual_value) if reserve_con.dual_value is not None else 0.0
```

The reserve MCP represents the marginal cost of providing one additional MW of reserve capacity system-wide.

## Finding Binding Lines

Lines at or near thermal limits (≥99% loading) cause congestion and LMP separation. See the `dc-power-flow` skill for the exact DC flow formula.

Key gotchas:
- Respect `BR_STATUS` (skip out-of-service branches).
- If `RATE_A <= 0`, treat as unconstrained.
- Include transformer `TAP` and phase-shifter `SHIFT` if present.

```python
import math

BINDING_THRESHOLD = 99.0  # Percent loading

binding_lines = []
for k, br in enumerate(branches):
    if int(br[10]) != 1:  # BR_STATUS
        continue

    x = float(br[3])
    rate = float(br[5])
    if x == 0.0 or rate <= 0.0:
        continue

    f = bus_num_to_idx[int(br[0])]
    t = bus_num_to_idx[int(br[1])]

    tap = float(br[8]) if len(br) > 8 else 0.0
    if tap == 0.0:
        tap = 1.0

    shift_deg = float(br[9]) if len(br) > 9 else 0.0
    shift_rad = math.radians(shift_deg)

    b_eff = (1.0 / x) / tap
    flow_MW = b_eff * (theta.value[f] - theta.value[t] - shift_rad) * baseMVA
    loading_pct = abs(flow_MW) / rate * 100.0

    if loading_pct >= BINDING_THRESHOLD:
        binding_lines.append({
            "from": int(br[0]),
            "to": int(br[1]),
            "flow_MW": round(float(flow_MW), 2),
            "limit_MW": round(float(rate), 2),
        })
```

## Counterfactual Analysis

To analyze the impact of relaxing a transmission constraint:

1. **Solve base case** — record costs, LMPs, and binding lines
2. **Modify constraint** — e.g., increase a line's thermal limit
3. **Solve counterfactual** — with the relaxed constraint
4. **Compute impact** — compare costs and LMPs

Implementation tips:
- Some cases may have **multiple parallel branches** between the same bus pair; decide whether to relax *all* matches or only the intended one.
- If you want a fully reusable approach without mutating the original branch array, create a `rate_overrides` dict keyed by branch index.

```python
# Identify matching branch indices (treat (f,t) and (t,f) as the same corridor)
branch_indices = []
for k in range(n_branch):
    br_from, br_to = int(branches[k, 0]), int(branches[k, 1])
    if (br_from == target_from and br_to == target_to) or \
       (br_from == target_to and br_to == target_from):
        branch_indices.append(k)

# Apply a 20% increase to all matches
rate_overrides = {}
for k in branch_indices:
    rate_overrides[k] = float(branches[k, 5]) * 1.20

# After solving both cases:
cost_reduction = base_cost - cf_cost  # Should be >= 0 (numerical noise aside)

# LMP changes per bus
for bus_num in base_lmp_map:
    delta = cf_lmp_map[bus_num] - base_lmp_map[bus_num]
    # Negative delta = price decreased (congestion relieved)

# Congestion relieved if adjusted corridor is not binding in the counterfactual
congestion_relieved = not is_binding_in_cf
```

### Economic Intuition

- **Relaxing a binding constraint** cannot increase cost (may decrease or stay same)
- **Cost reduction** quantifies the shadow price of the constraint
- **LMP convergence** after relieving congestion indicates reduced price separation
