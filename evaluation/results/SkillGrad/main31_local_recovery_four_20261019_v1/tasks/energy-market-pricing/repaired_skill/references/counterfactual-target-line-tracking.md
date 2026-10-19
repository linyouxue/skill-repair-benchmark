# Counterfactual target-line tracking (DC-OPF)

Use this when a counterfactual modifies a *specific* line/constraint (e.g., “increase the limit on line i→j”) and the report includes `congestion_relieved`, binding lines, or any narrative about that element becoming non-binding.

## Goal

Prevent internal contradictions by ensuring that:
- the target line is identified uniquely
- the target line’s loading/bindingness is computed from the **same solved state** (theta/dispatch) used for the `binding_lines` list
- `congestion_relieved` is derived from the target line’s bindingness, not from unrelated aggregates

## Step-by-step procedure

### 1) Identify the target line uniquely

Lines can be directional or duplicated; don’t assume `(from,to)` is unique without checking.

```python
import numpy as np

branches = np.asarray(branches)

f_bus = int(target_from_bus)
t_bus = int(target_to_bus)

cand = np.where((branches[:, 0].astype(int) == f_bus) & (branches[:, 1].astype(int) == t_bus))[0]
if cand.size != 1:
    raise ValueError(f"target line not unique: {(f_bus,t_bus)} has {cand.size} matches")

k = int(cand[0])
rate0_MW = float(branches[k, 5])
print("target branch index", k, "base rate", rate0_MW)
```

Runtime branch:
- If the dataset stores undirected lines as either direction, search both `(from,to)` and `(to,from)` and decide which one the task means; then apply the same choice consistently for base and counterfactual.

### 2) Define one flow/loading function and reuse it

```python
def flow_loading_MW(theta, *, branches, bus_num_to_idx, baseMVA, k: int):
    br = branches[k]
    f = bus_num_to_idx[int(br[0])]
    t = bus_num_to_idx[int(br[1])]
    x = float(br[3])
    rate_MW = float(br[5])
    if x == 0 or rate_MW <= 0:
        return 0.0, 0.0, rate_MW

    b = 1.0 / x
    flow_MW = b * (float(theta[f]) - float(theta[t])) * float(baseMVA)
    loading_pct = abs(flow_MW) / rate_MW * 100.0
    return flow_MW, loading_pct, rate_MW
```

### 3) After each solve, compute target-line bindingness + binding_lines from the same theta

```python
BINDING_THRESHOLD = 99.0

# Base solve outputs
flow0, load0, lim0 = flow_loading_MW(theta_base, branches=branches, bus_num_to_idx=bus_num_to_idx, baseMVA=baseMVA, k=k)
was_binding = (load0 >= BINDING_THRESHOLD)

# Counterfactual solve outputs
flow1, load1, lim1 = flow_loading_MW(theta_cf, branches=branches_cf, bus_num_to_idx=bus_num_to_idx, baseMVA=baseMVA, k=k)
is_binding = (load1 >= BINDING_THRESHOLD)

congestion_relieved = bool(was_binding and (not is_binding))

print({
    "target": {"from": f_bus, "to": t_bus, "k": k},
    "base": {"flow_MW": flow0, "loading_pct": load0, "limit_MW": lim0, "binding": was_binding},
    "cf": {"flow_MW": flow1, "loading_pct": load1, "limit_MW": lim1, "binding": is_binding},
    "congestion_relieved": congestion_relieved,
})
```

Runtime branch:
- If you solve in per-unit and keep `theta` in radians, the above still works so long as `x` is in per-unit and you apply `* baseMVA` to get MW. If your branch `x` is already in MW-normalized units, remove the `baseMVA` scaling and update both flow and limit units to match.

## Verification (must pass before writing the report)

1. **Target-line consistency**: recompute whether the target appears in your `binding_lines` list using the same `k`:
   - If `congestion_relieved` is `true` but `is_binding` is `true` → you have a calculation-path mismatch → **recompute flow/loading using the theta from the counterfactual solve**.
2. **Objective monotonicity**: if the counterfactual only relaxes constraints, `cf_cost` must not exceed `base_cost`.
   - If violated → you likely solved different objective functions, used different unit conversions, or did not reach optimality → **re-solve with identical objective/units and check solver status**.
3. **Units check**: `limit_MW` should be comparable to other line ratings; if `loading_pct` is extreme everywhere → **audit MW vs pu** (read `references/unit-audit.md`).
