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
Pshift = np.zeros(n_bus)  # phase-shift injections (pu), for Pg - Pd - Pshift = B @ theta

for br in branches:
    # Skip out-of-service branches (BR_STATUS at index 10)
    if int(br[10]) == 0:
        continue

    f = bus_num_to_idx[int(br[0])]  # Map bus number to index
    t = bus_num_to_idx[int(br[1])]
    x = br[3]  # Reactance
    if x == 0:
        continue

    # Transformer modeling (TAP at index 8, SHIFT at index 9 in degrees)
    tap = float(br[8]) if br[8] not in (0, None) else 1.0
    shift = np.deg2rad(float(br[9])) if len(br) > 9 else 0.0

    b = 1.0 / x

    # B matrix contributions with off-nominal tap
    B[f, f] += b / (tap * tap)
    B[t, t] += b
    B[f, t] -= b / tap
    B[t, f] -= b / tap

    # Phase shift modeled as constant injections
    if shift != 0.0:
        Pshift[f] += -(b / tap) * shift
        Pshift[t] += +(b / tap) * shift
```

## Power Balance Equation

At each bus: `Pg - Pd - Pshift = B[i, :] @ θ` (include `Pshift` if any in-service transformer has nonzero SHIFT)

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

# Skip out-of-service branches
if int(br[10]) == 0:
    continue

tap = float(br[8]) if br[8] not in (0, None) else 1.0
shift = np.deg2rad(float(br[9])) if len(br) > 9 else 0.0
b = 1.0 / br[3]  # Susceptance = 1/X

# Transformer DC flow model (tap + phase shift)
flow_pu = (b / tap) * ((theta[f] - theta[t]) - shift)
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
if int(br[10]) == 0:
    continue

tap = float(br[8]) if br[8] not in (0, None) else 1.0
shift = np.deg2rad(float(br[9])) if len(br) > 9 else 0.0
flow = (b / tap) * ((theta[f] - theta[t]) - shift) * baseMVA
constraints.append(flow <= rate)
constraints.append(flow >= -rate)
```
