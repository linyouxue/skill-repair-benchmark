# Counterfactual target-line tracking (DC congestion experiments)

Read this when a counterfactual modifies **one specific line/constraint** (uprate, relax limit, remove constraint) and you must report both:
- a per-target claim/flag (e.g., `congestion_relieved`), and
- a global list/count of `binding_lines` under a threshold rule.

The purpose is to keep *target* validation and *global* screening consistent.

## Worked procedure

### 1) Identify the target uniquely

Branch depending on whether line IDs are explicit.

```python
# Inputs: branch table with from_bus, to_bus, and (optional) unique line_id.
# Output: a single target index.

def find_target(branches, from_bus, to_bus, line_id=None):
    cands = []
    for k, br in enumerate(branches):
        fb, tb = int(br[0]), int(br[1])
        same_endpoints = {fb, tb} == {int(from_bus), int(to_bus)}
        if not same_endpoints:
            continue
        if line_id is None:
            cands.append(k)
        else:
            if str(br[2]) == str(line_id):
                cands.append(k)

    if len(cands) != 1:
        raise ValueError(f"target not unique; candidates={cands}")
    return cands[0]
```

### 2) Compute flow/loading consistently (same solve, same units)

```python
def line_flow_loading_MW(branch_row, theta, bus_num_to_idx, baseMVA):
    fb, tb = int(branch_row[0]), int(branch_row[1])
    x = float(branch_row[3])
    rate_MW = float(branch_row[5])

    f = bus_num_to_idx[fb]
    t = bus_num_to_idx[tb]

    if x == 0 or rate_MW <= 0:
        return 0.0, 0.0

    b = 1.0 / x
    flow_MW = b * (float(theta[f]) - float(theta[t])) * float(baseMVA)
    loading_pct = abs(flow_MW) / rate_MW * 100.0
    return flow_MW, loading_pct
```

### 3) Solve base and counterfactual; record target metrics

Runtime branch: you may discover the target was never binding in base.

```python
THRESH = 99.0

base_flow, base_load = line_flow_loading_MW(branches[target_k], theta_base, bus_num_to_idx, baseMVA)
cf_flow, cf_load = line_flow_loading_MW(branches[target_k], theta_cf, bus_num_to_idx, baseMVA)

was_binding = base_load >= THRESH
is_binding_cf = cf_load >= THRESH

if not was_binding:
    congestion_relieved = False  # you cannot "relieve" a non-binding constraint
else:
    congestion_relieved = (not is_binding_cf)
```

### 4) Reconcile target claim with global binding-lines list

```python
def in_binding_lines(binding_lines, from_bus, to_bus):
    tgt = {int(from_bus), int(to_bus)}
    return any({int(e["from"]), int(e["to"])} == tgt for e in binding_lines)

# After you compute counterfactual binding_lines from theta_cf:

if congestion_relieved:
    assert not in_binding_lines(binding_lines_cf, branches[target_k][0], branches[target_k][1])
```

## Verification step (must prescribe corrective action)

1. If `find_target` raises because the target is not unique: add a disambiguator (explicit line_id/index, circuit number) and re-identify; do not proceed with an arbitrary candidate.
2. If the target metrics say “relieved” but it still appears in `binding_lines_cf`: recompute `binding_lines_cf` from the final counterfactual `theta` using the *same* `line_flow_loading_MW` function and unit conversions.
3. If `congestion_relieved` is `True` but `was_binding` is `False`: rewrite the report semantics (it was never congested) or adjust the threshold only if the task definition differs; then re-run checks.
