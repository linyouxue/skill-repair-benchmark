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



## End-to-End DC-OPF with Reserve Co-Optimization and Counterfactual Pricing

Use the following procedure for MATPOWER-format `network.json` cases. Keep all bus IDs in reports, while using the explicit bus-number-to-array-index mapping internally.

1. **Parse and normalize the case.** Read `baseMVA`, `bus`, `gen`, and `branch`. Build `bus_num_to_idx` from the bus-number column and map every generator and branch endpoint through it; never use `bus_number - 1`. Read generator limits and costs from the MATPOWER columns, and use `RATE_A` as the thermal limit. Reject or explicitly handle missing/zero reactance and missing thermal ratings rather than silently creating an unconstrained or infinite-flow branch.

2. **Construct the DC network.** For each branch with nonzero reactance `x`, use `b = 1/x` and the mapped endpoints. Define the oriented flow exactly as stored in the branch record:
   `F_l = baseMVA * b_l * (theta[f_l] - theta[t_l])`.
   Retain this orientation for reporting, but use `abs(F_l)` for loading. Enforce both `F_l <= limit_l` and `F_l >= -limit_l` in every optimization scenario. Fix the angle of the MATPOWER reference/slack bus (type 3) to zero, and fail clearly if no unique reference bus is available.

3. **Build the reserve-cooptimized OPF.** Use variables `Pg_g`, upward spinning reserve `R_g`, and bus angles `theta_i`. For every generator enforce its operating and capacity-coupling limits, including `Pmin_g <= Pg_g`, `Pg_g + R_g <= Pmax_g`, and `R_g >= 0`; include any additional generator availability or reserve limits present in the input. Enforce nodal balance in consistent MW units at every bus:
   `sum(Pg at i) - Pd_i = sum(F_l leaving i)`.
   Apply the stated spinning-reserve requirement from the task/case data, and use the standard capacity-coupled reserve formulation rather than allowing reserve to exceed unused generator capacity. Minimize the complete generation-plus-reserve offer cost represented by the input data, preserving all piecewise-linear or segmented cost details when present. Do not invent costs or a reserve requirement when they are absent; identify the missing specification instead.

4. **Run exactly two scenarios from the same parsed base data.** In the base scenario, use every original branch limit unchanged. Identify target branches by endpoint set `{64, 1501}`, independent of stored endpoint order. Preserve their original orientation and branch indices. Explicitly collect all matches: if parallel 64--1501 records exist, treat the matching records as the target set and increase only those records' counterfactual `RATE_A` values by `1.20`; do not modify any nonmatching branch or the base data in place. In the counterfactual scenario, all other limits, reactances, loads, generators, costs, and reserve requirements must remain identical.

5. **Extract and verify market outputs.** Report total objective value in dollars per hour using the case's monetary scaling. Obtain each bus LMP from the dual of that bus's nodal-balance equality, applying the solver's documented equality-dual sign convention so that an additional MW of demand has a positive marginal price. Obtain the system reserve MCP from the dual of the reserve requirement, with the same unit and sign normalization. If reserve is nonbinding, report the correctly normalized zero/marginal dual rather than a generator offer guessed from the dispatch.

6. **Classify and report transmission constraints.** Recompute every branch flow from the solved angles (not from rounded output). Compute `loading_pct = abs(flow_MW) / original_or_scenario_limit_MW * 100`. A branch is binding when `loading_pct >= 99`; include its original `from` and `to` bus IDs, signed oriented `flow_MW`, and the applicable scenario `limit_MW`. The target branch's counterfactual limit is the only changed limit, and parallel target records must be reported separately.

7. **Validate before writing `report.json`.** Check every bus balance residual, generator/reserve coupling inequality, reserve requirement, two-sided flow limit, and reference-angle constraint against a documented numerical tolerance. Confirm that base limits equal the input limits and that counterfactual limits differ only for the identified 64--1501 target records, by exactly 20%. Compare scenarios using unrounded values: `cost_reduction = base_cost - cf_cost`; compute each bus's `delta = cf_lmp - base_lmp`, sort ascending by delta, and return the three largest LMP drops (or all available buses if fewer than three). Set `congestion_relieved` to true exactly when the adjusted target line or target-line set is not binding in the counterfactual scenario; otherwise set it false. Ensure every bus appears once in each LMP list and that report field names and units match the requested JSON schema.
