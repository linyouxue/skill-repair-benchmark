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

Build from branch reactances using bus number mapping.

### Taps and phase shifters (MATPOWER DC model)

For the standard MATPOWER DC formulation (see `makeBdc.m`), the *series susceptance* is:

- `b = status / x`
- `tap = 1.0 if TAP==0 else TAP`
- effective `b_eff = b / tap`

and the bus injections include a phase-shift term:

- `Pfinj = b_eff * (-SHIFT_rad)` injected at the **from** bus
- `Pbusinj = Cft.T @ Pfinj`

This means you can write the nodal balance compactly as:

`Ag @ Pg - Pd_pu - Gs_pu == Bbus @ theta + Pbusinj`

(Where `Bbus = Cft.T @ Bf` with `Bf` built from `b_eff`.)

```python
bus_num_to_idx = {int(buses[i, 0]): i for i in range(n_bus)}
B = np.zeros((n_bus, n_bus))
shift_inj = np.zeros(n_bus)
Gs_pu = buses[:, 4] / baseMVA  # shunt conductance MW at V=1.0 pu (often 0)

for br in branches:
    if int(br[10]) != 1:  # BR_STATUS
        continue

    f = bus_num_to_idx[int(br[0])]
    t = bus_num_to_idx[int(br[1])]

    x = float(br[3])
    if x == 0.0:
        continue

    tap = float(br[8]) if len(br) > 8 else 0.0
    if tap == 0.0:
        tap = 1.0

    b_eff = (1.0 / x) / tap

    B[f, f] += b_eff
    B[t, t] += b_eff
    B[f, t] -= b_eff
    B[t, f] -= b_eff

    shift_deg = float(br[9]) if len(br) > 9 else 0.0
    if shift_deg != 0.0:
        shift_rad = shift_deg * np.pi / 180.0
        shift_inj[f] += -b_eff * shift_rad
        shift_inj[t] += +b_eff * shift_rad
```

**Notes**
- Some texts use a `1/tap^2` term in the diagonal for transformer models. MATPOWER’s *DC* helper `makeBdc` uses `b/tap` in both diagonal and off-diagonal terms (with phase shifts handled via injections as above). Match the conventions of your dataset/toolchain.

## Power Balance Equation

At each bus (DC approximation):

`Pg_pu - Pd_pu - Gs_pu == B[i, :] @ θ + shift_inj[i]`

Where:
- `Pg_pu` = net generation injected at bus (per-unit)
- `Pd_pu` = fixed demand at bus (per-unit)
- `Gs_pu` = shunt conductance at bus (per-unit, MW at V=1.0 pu divided by baseMVA)
- `θ` = vector of bus angles (radians)
- `shift_inj` = phase-shifter injection term (per-unit), **0** if no phase shifters

If you build `B` without phase-shifter injections, omit `shift_inj`. If your model ignores shunt conductance, set `Gs_pu = 0`.

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

Flow on branch from bus f to bus t (use bus number mapping). **Handle taps and phase shifters** when present in MATPOWER branch data:

```python
import math

f = bus_num_to_idx[int(br[0])]
t = bus_num_to_idx[int(br[1])]

x = br[3]
tap = br[8] if len(br) > 8 else 0.0
shift_deg = br[9] if len(br) > 9 else 0.0

# MATPOWER: tap=0 means 1.0; phase shift is degrees
if tap == 0:
    tap = 1.0
shift_rad = shift_deg * math.pi / 180.0

# DC branch susceptance with tap
b = (1.0 / x) / tap

flow_pu = b * (theta[f] - theta[t] - shift_rad)
flow_MW = flow_pu * baseMVA
```

## Line Loading Percentage

```python
loading_pct = abs(flow_MW) / rating_MW * 100
```

Where `rating_MW = branch[5]` (RATE_A column).

Note: If RATE_A is 0, treat the line as unconstrained (skip adding flow limit constraints and skip loading percentage checks).

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
