---
name: locational-marginal-prices
description: "Extract locational marginal prices (LMPs) from DC-OPF solutions using dual values. Use when computing nodal electricity prices, reserve clearing prices, or performing price impact analysis."
---

# Locational Marginal Prices (LMPs)

LMPs are the marginal cost of serving one additional MW of load at each bus. In optimization terms, they are the **dual values** (shadow prices) of the nodal power balance constraints.



A canonical DC-OPF nodal balance equation is:

```python
# Net injection equals net network export
pg_at_bus - pd == B[i, :] @ theta
```

where:
- `pg_at_bus` is total generation injection at the bus (positive)
- `pd` is load withdrawal at the bus (positive demand)
- `B[i, :] @ theta` is net export from the bus into the network

Equivalent rearrangements such as `pg_at_bus - pd - B[i, :] @ theta == 0` are fine if used consistently. However, reversing the equality direction (for example `B[i, :] @ theta == pg_at_bus - pd` versus `pg_at_bus - pd == B[i, :] @ theta`) changes the sign convention of the reported dual values in some solvers. Always verify the resulting LMP sign convention against economic intuition.



## Units, Dual Scaling, and Sign (Most Common LMP Pitfalls)

Very large LMP magnitudes (e.g., **1e4–1e6 $/MWh**) almost always indicate a **unit inconsistency** and/or **dual sign interpretation error**.

### Canonical convention (recommended)
Use a single, consistent nodal balance form and interpret duals relative to it:

- **Balance equation (MW or p.u.)**:
  
  \(\text{generation} - \text{load} - \text{net export} = 0\)

In code (same as above):
```python
pg_at_bus - pd - (B[i, :] @ theta) == 0
```
If you instead write an algebraically equivalent equality with reversed sides, some solvers report the dual with the opposite sign. When in doubt, prefer the explicit “`... == 0`” form.

### What units should the dual have?
Let the objective be in **$ per hour** and loads/generation be in either **MW** or **per-unit (p.u.) on baseMVA**.

- If variables/parameters in the balance constraint are in **MW**, then the balance dual has units **$/MW-h = $/MWh**. In that case, you typically use:
  
  \(\text{LMP}_i \approx \lambda_i\) (up to a sign convention; see below).

- If the balance is written in **p.u.**, then 1 p.u. = baseMVA MW. The dual is in **$/(p.u.-h)**. Convert to $/MWh by:
  
  \(\text{LMP}_i[\$/\text{MWh}] = \lambda_i[\$/\text{p.u.-h}] \;/\; \text{baseMVA}\)
  
  (Equivalently, multiply by \(1/\text{baseMVA}\).)

**Rule of thumb:** dual × (units of constraint LHS) ≈ $/h. So divide/multiply by baseMVA so that the final result is $/MWh.

### Equality orientation and sign
For an equality constraint \(h(x)=0\), the reported dual can flip sign depending on whether you entered \(h(x)=0\) or \(-h(x)=0\), or whether you wrote `lhs == rhs` vs `rhs == lhs`. Therefore:

- After computing tentative LMPs, validate by economics:
  - In an **uncongested** system with no binding line limits, LMPs should be **nearly uniform** across buses.
  - The common LMP should be close to the **marginal energy cost** of the marginal generator.
  - Typical magnitudes are **tens to hundreds of $/MWh** (occasionally thousands in extreme scarcity/congestion), not 1e5.

### Quick dimensional-analysis examples
- **MW formulation**: objective $/h, balance in MW ⇒ dual is $/(MW·h) = $/MWh.
- **p.u. formulation**: objective $/h, balance in p.u. ⇒ dual is $/(p.u.·h). Since 1 p.u. = baseMVA MW, divide by baseMVA to get $/MWh.

### Sanity checks when you see huge prices
If you see LMPs around 1e4–1e6:
1. Confirm whether `Pd` and `Pg` are in MW or p.u. (mixing MW and p.u. in the same balance is a common cause).
2. Confirm whether `B @ theta` is in the same units as injections (often `B` is built assuming p.u.).
3. Re-check the baseMVA conversion direction (divide vs multiply).
4. Check whether you need a sign flip due to equality orientation.
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
    pd = buses[i, 2] / baseMVA

    # Create constraint and store reference
    balance_con = pg_at_bus - pd == B[i, :] @ theta
    balance_constraints.append(balance_con)
    constraints.append(balance_con)

# Solve
prob = cp.Problem(cp.Minimize(cost), constraints)
prob.solve(solver=cp.CLARABEL)

# Extract LMPs from duals
lmp_by_bus = []
for i in range(n_bus):
    bus_num = int(buses[i, 0])
    dual_val = balance_constraints[i].dual_value

    # Scale carefully (most common source of 1e4–1e6 “LMPs”):
    # - If balance is written in MW: dual is already in $/MWh (up to sign).
    # - If balance is written in per-unit on baseMVA: dual is in $/(p.u.-h)
    #   and you must DIVIDE by baseMVA to get $/MWh.
    # Choose ONE consistent convention and verify with sanity checks.
    if dual_val is None:
        lmp = 0.0
    else:
        lmp = float(dual_val) / baseMVA  # for p.u. balance; use *=1.0 if MW balance

    lmp_by_bus.append({


    # If your balance equation orientation is reversed, the economically
    # correct LMP may require a sign flip.
    # Example consistency check in an uncongested system:
    # - all buses should have nearly identical LMPs
    # - the common LMP should approximately match the marginal generator cost
    #   of the marginal unit serving an incremental MW of demand
        "bus": bus_num,
        "lmp_dollars_per_MWh": round(lmp, 2)
    })
```

## LMP Sign Convention


A practical way to lock down sign is to define LMP as the marginal increase in optimal objective when **increasing load** at a bus by 1 MW:

- Perturbation definition:
  \(\text{LMP}_i = \frac{\partial \text{OptimalCost}}{\partial P_{d,i}}\) in $/MWh.

If your balance is written as `pg - pd - net_export == 0`, then increasing `pd` by +1 MW shifts the constraint by −1 MW; depending on solver dual sign conventions, the raw dual may need a sign flip to match the perturbation definition. Validate by checking that increasing load at a normal bus should **not** reduce cost in an uncongested, non-pathological case.
For a balance constraint written as `generation - load == net_export`:
- **Positive LMP**: Increasing load at that bus increases total cost (typical case)
- **Negative LMP**: Increasing load at that bus *decreases* total cost

If you instead formulate the balance equation with the opposite orientation, many solvers will return duals with the opposite sign. A quick validation is to solve an uncongested case: all buses should clear at approximately the same energy price, and that price should align with the marginal production cost of the marginal generator.

Negative LMPs commonly occur when:
- Cheap generation is trapped behind a congested line (can't export power)
- Adding load at that bus relieves congestion by consuming local excess generation
- The magnitude can be very large in heavily congested networks (thousands of $/MWh)

Negative LMPs are physically valid and expected in congested systems — they are not errors.



## Magnitude Sanity Checks (catch unit bugs early)

Use these quick checks before trusting prices:

- **Uniformity check (no congestion):** If you temporarily relax all line limits (or in a known uncongested case), LMPs should be nearly identical across buses.
- **Marginal cost check:** The (nearly uniform) LMP should be close to the marginal generator’s cost (e.g., $20–$200/MWh in many test cases).
- **Order-of-magnitude check:** If you see LMPs like 100,000 $/MWh, you almost certainly have:
  - MW vs p.u. mixing in the balance equation, and/or
  - baseMVA conversion in the wrong direction, and/or
  - a sign/orientation mismatch.

These checks are complementary to feasibility/optimality; a feasible OPF can still yield meaningless LMPs if units/signs are mishandled.
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

Lines at or near thermal limits (≥99% loading) cause congestion and LMP separation. See the `dc-power-flow` skill for line flow calculation details.

```python
BINDING_THRESHOLD = 99.0  # Percent loading

binding_lines = []
for k, br in enumerate(branches):
    f = bus_num_to_idx[int(br[0])]
    t = bus_num_to_idx[int(br[1])]
    x, rate = br[3], br[5]

    if x != 0 and rate > 0:
        b = 1.0 / x
        flow_MW = b * (theta.value[f] - theta.value[t]) * baseMVA
        loading_pct = abs(flow_MW) / rate * 100

        if loading_pct >= BINDING_THRESHOLD:
            binding_lines.append({
                "from": int(br[0]),
                "to": int(br[1]),
                "flow_MW": round(float(flow_MW), 2),
                "limit_MW": round(float(rate), 2)
            })
```

## Counterfactual Analysis

To analyze the impact of relaxing a transmission constraint:

1. **Solve base case** — record costs, LMPs, and binding lines
2. **Modify constraint** — e.g., increase a line's thermal limit
3. **Solve counterfactual** — with the relaxed constraint
4. **Compute impact** — compare costs and LMPs

```python
# Modify line limit (e.g., increase by 20%)
for k in range(n_branch):
    br_from, br_to = int(branches[k, 0]), int(branches[k, 1])
    if (br_from == target_from and br_to == target_to) or \
       (br_from == target_to and br_to == target_from):
        branches[k, 5] *= 1.20  # 20% increase
        break

# After solving both cases:
cost_reduction = base_cost - cf_cost  # Should be >= 0

# LMP changes per bus
for bus_num in base_lmp_map:
    delta = cf_lmp_map[bus_num] - base_lmp_map[bus_num]
    # Negative delta = price decreased (congestion relieved)

# Congestion relieved if line was binding in base but not in counterfactual
congestion_relieved = was_binding_in_base and not is_binding_in_cf
```

### Economic Intuition

- **Relaxing a binding constraint** cannot increase cost (may decrease or stay same)
- **Cost reduction** quantifies the shadow price of the constraint
- **LMP convergence** after relieving congestion indicates reduced price separation
