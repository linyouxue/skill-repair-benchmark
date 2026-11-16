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

## Susceptance Matrix (B) — MATPOWER DC conventions

Build from branch reactances using bus number mapping **and** MATPOWER transformer/phase-shifter conventions.

MATPOWER `branch` columns used here:
- `X` = `branch[:, 3]`
- `TAP` = `branch[:, 8]` (transformer off-nominal tap; **if 0, interpret as 1.0**)
- `SHIFT` = `branch[:, 9]` (phase shift in **degrees**)

For DC, the series susceptance is `b = 1/X` and transformer tap modifies the “from-side” coupling. For building the B (Bbus) matrix consistent with MATPOWER’s DC model:
- use `tau = (TAP if TAP != 0 else 1.0)`
- add to diagonals/off-diagonals using `b/tau^2` on the from-bus diagonal and `b/tau` on the off-diagonal terms.
- `SHIFT` affects the *right-hand-side injection* terms, not the symmetric B matrix (see Line Flow section for explicit flow equation).

```python
import numpy as np

bus_num_to_idx = {int(buses[i, 0]): i for i in range(n_bus)}
B = np.zeros((n_bus, n_bus))

for br in branches:
    f = bus_num_to_idx[int(br[0])]
    t = bus_num_to_idx[int(br[1])]
    x = float(br[3])
    if x == 0:
        continue
    b = 1.0 / x

    tap = float(br[8]) if len(br) > 8 else 0.0
    tau = tap if tap not in (0.0, -0.0) else 1.0  # MATPOWER: TAP=0 means 1.0

    # Bbus contributions (MATPOWER-style DC with taps)
    B[f, f] += b / (tau * tau)
    B[t, t] += b
    B[f, t] -= b / tau
    B[t, f] -= b / tau
```

If you also build an injection offset vector for phase shifters (recommended for OPF): for each branch, add `(+b*shift_rad/tau)` to the from-bus injection and `(-b*shift_rad/tau)` to the to-bus injection (see canonical flow equation below).

## Power Balance Equation

At each bus: `Pg - Pd = B[i, :] @ θ`

Where:
- Pg = generation at bus (pu)
- Pd = load at bus (pu)
- θ = vector of bus angles (radians)

## Slack/Reference Bus and Sign Conventions

One bus angle must be fixed as the reference (θ = 0) to remove the singularity of B.

- Use MATPOWER bus type `type=3` as the reference if present.
- Sign convention: **net injection** at bus *i* is `Pinj_i = Pg_i - Pd_i` (MW or pu consistently). Positive means net generation.
- Line flow sign: `P_ft` is positive when flowing **from** bus `F_BUS` **to** bus `T_BUS`.

```python
slack_idx = None
for i in range(n_bus):
    if int(buses[i, 1]) == 3:
        slack_idx = i
        break
if slack_idx is None:
    raise ValueError("No slack/reference bus (type=3) found")
constraints.append(theta[slack_idx] == 0)
```

Implementation note: If you instead solve a reduced system, remove the slack row/column of B and the slack entry of θ, then back-fill θ_slack=0.

## Line Flow Calculation (canonical DC with TAP and SHIFT)

Use MATPOWER’s DC branch flow convention including transformer off-nominal tap and phase shifter.

Given:
- `b = 1/X`
- `tau = (TAP if TAP != 0 else 1.0)`
- `phi = SHIFT * pi/180` (radians)

Canonical DC real-power flow **from f to t**:

`P_ft (pu) = (b / tau) * ( theta[f] - theta[t] - phi )`

Convert to MW by multiplying by `baseMVA`.

```python
import numpy as np

f = bus_num_to_idx[int(br[0])]
t = bus_num_to_idx[int(br[1])]

x = float(br[3])
b = 1.0 / x

tap = float(br[8]) if len(br) > 8 else 0.0
	au = tap if tap not in (0.0, -0.0) else 1.0  # MATPOWER: TAP=0 means 1.0

shift_deg = float(br[9]) if len(br) > 9 else 0.0
phi = shift_deg * np.pi / 180.0

flow_pu = (b / tau) * (theta[f] - theta[t] - phi)
flow_MW = flow_pu * baseMVA
```

Notes:
- If `SHIFT=0` and `TAP=1`, this reduces to `b*(θf-θt)`.
- The opposite-direction flow is `P_tf = -P_ft` under this DC model.

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

## Thermal Limits (RATE_A) for OPF

MATPOWER `RATE_A` (`branch[:,5]`) is a long-term MVA rating; under DC with |V|≈1 it is treated as an MW limit. Enforce it as a **symmetric** bound on real-power flow:

- If `RATE_A <= 0` (or missing), treat as **no binding thermal limit** (skip constraint).
- Otherwise enforce: `-RATE_A <= P_ft_MW <= RATE_A`.

```python
rate = float(br[5])
if rate > 0:
    constraints.append(flow_MW <= rate)
    constraints.append(flow_MW >= -rate)
```

## Validation / Consistency Checks (recommended)

To avoid “internally feasible but wrong optimum” outcomes, validate DC network modeling against MATPOWER conventions:

1. **Tap/shift sanity**
   - Verify all `TAP==0` are interpreted as `1.0`.
   - Convert `SHIFT` from degrees to radians.

2. **Flow consistency checks**
   - After solving for θ, compute each branch flow using the canonical formula above.
   - Independently compute flows using an incidence-based formulation or PTDF (if available) and confirm max absolute difference is small (numerical tolerance).

3. **Nodal balance check**
   - Compute net injections `Pinj = Pg - Pd`.
   - Compute implied injections from network: `B @ theta + Pshift`, where `Pshift` is the phase-shift injection offset vector (from the B-building section).
   - Confirm `Pinj` matches within tolerance at all buses (except for any modeled slack/penalty mechanisms).

4. **Binding line identification**
   - Use the same `P_ft_MW` that appears in constraints.
   - Mark binding if `abs(P_ft_MW) >= 0.99 * RATE_A` (and `RATE_A > 0`).

These checks catch the most common MATPOWER DC edge cases (TAP=0, phase shifters, sign conventions, and inconsistent constraint vs reporting flows).
