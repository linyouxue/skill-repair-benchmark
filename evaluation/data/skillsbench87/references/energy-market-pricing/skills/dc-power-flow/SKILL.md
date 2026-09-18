---
name: dc-power-flow
description: "DC power flow analysis for power systems. Use when computing power flows using DC approximation, building susceptance matrices, calculating line flows and loading percentages, or performing sensitivity analysis on transmission networks."
---

# DC Power Flow

DC power flow is a linearized approximation of AC power flow, suitable for economic dispatch and contingency analysis.

## DC Approximations

1. **Lossless lines** - Ignore resistance (R ≈ 0)
2. **Flat voltage** - All bus voltages = 1.0 pu
3. **Small angles** - sin(θ) ≈ θ, cos(θ) ≈ 1

Result: Power flow depends only on bus angles (θ) and line reactances (X).

## Frozen Model Contract

Freeze the DC equations before coding. A file described as “MATPOWER format”
defines an input schema; that phrase alone does not select every MATPOWER
transformer extension.

Unless the task explicitly writes an extended tap/phase equation, this Skill's
required model is:

- `b = 1 / X`
- `flow = b * (theta_from - theta_to) * baseMVA`
- symmetric B-matrix updates with `+b` on both diagonals and `-b` on both
  off-diagonals
- zero phase-offset injection

Use that one contract for the matrix, nodal balance, reported branch flows, and
thermal constraints. Use one shared model-building function for paired
base/counterfactual studies and change only the task-designated parameter.
Transformer tap ratios, phase shifts, line charging, and resistance enter the
model only when the task explicitly specifies their equations.

### Canonical sparse incidence construction

For a large network, preserve each branch's from/to pairing with this exact
layout:

```python
edge = np.arange(n_branch)
A = sp.coo_matrix(
    (
        np.r_[np.ones(n_branch), -np.ones(n_branch)],
        (np.r_[edge, edge], np.r_[f_idx, t_idx]),
    ),
    shape=(n_branch, n_bus),
).tocsr()

b = 1.0 / x
B = (A.T @ sp.diags(b) @ A).tocsr()
flow_MW = cp.multiply(b * baseMVA, A @ theta)
```

Before solving, require these structural checks:

```python
ones_bus = np.ones(n_bus)
assert np.all(A.getnnz(axis=1) == 2)
assert np.allclose(A @ ones_bus, 0.0)
assert np.allclose((B - B.T).data, 0.0)
assert np.allclose(B @ ones_bus, 0.0)
```

### Infeasibility debug order

An unexpected infeasible result first triggers an implementation audit:

1. verify bus-number mapping and each incidence row's `+1 @ from`,
   `-1 @ to` pairing;
2. verify MW versus per-unit conversions;
3. solve power balance and generator bounds before adding reserve and thermal
   constraint groups;
4. add constraint groups back one at a time and identify the first group that
   changes feasibility.

Keep the frozen equations during this audit. Change the physical formulation
only when the task itself explicitly requires a different equation.

Before export, require all of the following: `b == 1/X`, phase offset is zero,
B/flow construction does not consume transformer tap or phase-shift columns,
both scenarios use the same builder, and flows, nodal residuals, and total
objective have been independently recomputed from the submitted solution.

## Bus Number Mapping

Power system bus numbers may not be contiguous (e.g., case300 has non-sequential bus IDs). Always create a mapping from bus numbers to 0-indexed array positions:

```python
# Create mapping: bus_number -> 0-indexed position
bus_num_to_idx = {int(buses[i, 0]): i for i in range(n_bus)}

# Use mapping for branch endpoints
f = bus_num_to_idx[int(br[0])]  # NOT br[0] - 1
t = bus_num_to_idx[int(br[1])]
```

## Susceptance Matrix (B)

Build from branch reactances using bus number mapping:

```python
# Run: scripts/build_b_matrix.py
# Or inline:
bus_num_to_idx = {int(buses[i, 0]): i for i in range(n_bus)}
B = np.zeros((n_bus, n_bus))

for br in branches:
    f = bus_num_to_idx[int(br[0])]  # Map bus number to index
    t = bus_num_to_idx[int(br[1])]
    x = br[3]  # Reactance
    if x != 0:
        b = 1.0 / x
        B[f, f] += b
        B[t, t] += b
        B[f, t] -= b
        B[t, f] -= b
```

## Power Balance Equation

At each bus: `Pg - Pd = B[i, :] @ θ`

Where:
- Pg = generation at bus (pu)
- Pd = load at bus (pu)
- θ = vector of bus angles (radians)

## Slack Bus

One bus must have θ = 0 as reference. Find slack bus (type=3):

```python
slack_idx = None
for i in range(n_bus):
    if buses[i, 1] == 3:
        slack_idx = i
        break
constraints.append(theta[slack_idx] == 0)
```

## Line Flow Calculation

Flow on branch from bus f to bus t (use bus number mapping):

```python
f = bus_num_to_idx[int(br[0])]
t = bus_num_to_idx[int(br[1])]
b = 1.0 / br[3]  # Susceptance = 1/X
flow_pu = b * (theta[f] - theta[t])
flow_MW = flow_pu * baseMVA
```

## Line Loading Percentage

```python
loading_pct = abs(flow_MW) / rating_MW * 100
```

Where `rating_MW = branch[5]` (RATE_A column).

## Branch Susceptances for Constraints

Store susceptances when building constraints:

```python
branch_susceptances = []
for br in branches:
    x = br[3]
    b = 1.0 / x if x != 0 else 0
    branch_susceptances.append(b)
```

## Line Flow Limits (for OPF)

Enforce thermal limits as linear constraints:

```python
# |flow| <= rating  →  -rating <= flow <= rating
flow = b * (theta[f] - theta[t]) * baseMVA
constraints.append(flow <= rate)
constraints.append(flow >= -rate)
```
