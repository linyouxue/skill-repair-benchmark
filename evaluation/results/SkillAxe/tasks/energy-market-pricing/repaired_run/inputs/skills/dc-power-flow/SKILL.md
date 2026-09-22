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

### Transformers (tap ratio) and phase shifters (angle shift)

Many MATPOWER networks include off-nominal taps and phase shifts in the branch table.
If you ignore them, DC-OPF line flows and limits can be materially wrong.

MATPOWER branch columns (0-indexed, common convention):
- `TAP` at index 8 (0 means 1.0)
- `SHIFT` at index 9 (degrees)
- `BR_STATUS` at index 10 (1 in-service, 0 out)

A commonly used DC approximation for an in-service branch is:

- Let `tap = branch[k,8]` (use 1.0 if 0)
- Let `phi = deg2rad(branch[k,9])`
- Let `b = 1/x`

Then the real-power flow from f→t (MW) can be modeled as:

```python
tap = br[8] if br[8] != 0 else 1.0
phi = np.deg2rad(br[9])
b = 1.0 / br[3]
flow_MW = baseMVA * (b / tap) * ((theta[f] - theta[t]) - phi)
```

Notes:
- If `SHIFT=0`, this reduces to a tap-only model.
- If `TAP=1`, it reduces to a phase-shifter model.
- Always **skip** out-of-service branches (`BR_STATUS != 1`).

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

### Practical limit-handling rules

- **Respect branch status:** only enforce limits for `BR_STATUS == 1`.
- **RATE_A can be 0 or negative** in some datasets, meaning “no limit specified”.
  Do **not** constrain such lines; otherwise you can accidentally force flow≈0 and distort the optimum.

Example:

```python
status = int(br[10])
rate = float(br[5])
if status == 1 and rate > 0:
    # include -rate <= flow <= rate
    ...
```

- For tap/shift branches, use the tap/shift-aware flow expression from above.
