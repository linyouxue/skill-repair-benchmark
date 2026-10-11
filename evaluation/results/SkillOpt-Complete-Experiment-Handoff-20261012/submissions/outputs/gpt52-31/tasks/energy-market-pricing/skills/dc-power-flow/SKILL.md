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



## MATPOWER Branch Data and DC-OPF Handling

MATPOWER branch columns commonly used in DC-OPF:
- `br[0]` = F_BUS
- `br[1]` = T_BUS
- `br[2]` = BR_R
- `br[3]` = BR_X
- `br[5]` = RATE_A (MW thermal limit)
- `br[8]` = TAP
- `br[9]` = SHIFT (degrees)
- `br[10]` = BR_STATUS (1=in service, 0=out of service)

Always use bus-number mapping for F_BUS/T_BUS because bus IDs may be non-contiguous.

Skip out-of-service branches:

```python
if int(br[10]) == 0:
    continue
```

Treat `RATE_A <= 0` as unconstrained unless the task or dataset specifies otherwise.

For ordinary active lines without transformer effects:

```python
flow_MW = baseMVA * (theta[f] - theta[t]) / x
```

Equivalent per-unit limit form:

```python
flow_pu = (theta[f] - theta[t]) / x
-rate/baseMVA <= flow_pu <= rate/baseMVA
```

If non-unity transformer taps or phase shifts are present, use the adjusted DC flow:

```python
tap = br[8] if br[8] != 0 else 1.0
shift_rad = np.deg2rad(br[9])
flow_pu = ((theta[f] - theta[t]) - shift_rad) / (x * tap)
flow_MW = flow_pu * baseMVA
```

The sign convention is positive flow from F_BUS to T_BUS.

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

Enforce thermal limits only for active branches with positive RATE_A:

```python
if int(br[10]) == 1:  # BR_STATUS
    rate = br[5]      # RATE_A in MW

    if rate > 0:
        flow = b * (theta[f] - theta[t]) * baseMVA
        constraints.append(flow <= rate)
        constraints.append(flow >= -rate)
```

Report binding or nearly binding lines using a 99% threshold:

```python
if rate > 0 and abs(flow_MW) >= 0.99 * rate:
    binding_lines.append({
        "from": int(br[0]),
        "to": int(br[1]),
        "flow_MW": float(flow_MW),
        "limit_MW": float(rate),
    })
```



## Counterfactual Branch-Limit Modification

To modify the line connecting buses 64 and 1501, search branches in either orientation:

```python
is_target = (
    (int(br[0]) == 64 and int(br[1]) == 1501) or
    (int(br[0]) == 1501 and int(br[1]) == 64)
)
```

Apply the counterfactual only to that branch and only to its thermal capacity:

```python
if is_target and br[5] > 0:
    br_cf = br.copy()
    br_cf[5] = 1.2 * br[5]  # increase RATE_A by 20%
```

Do not modify reactance, topology, generator limits, reserve requirements, or other branch ratings.
