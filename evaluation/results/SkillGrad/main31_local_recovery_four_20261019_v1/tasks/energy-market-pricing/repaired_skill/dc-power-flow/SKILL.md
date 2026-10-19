---
name: dc-power-flow
description: "DC power flow analysis for power systems, including susceptance matrices, line flows, and thermal loading checks."
---

# DC Power Flow

DC power flow is a linearized approximation of AC power flow, suitable for OPF and congestion analysis.

## Artifact capture audit (workflow)

Before finalizing, ensure required deliverables are written to a grader-captured location and are externally visible.

1. Write artifacts to the task workspace (avoid virtualenv/system directories).
2. Confirm location and presence (`pwd`, `ls -la`).
3. Print a small preview and checksum to prove the file is real.

```python
from pathlib import Path
import hashlib

p = Path("output.json")
assert p.exists() and p.is_file()
blob = p.read_bytes()
print(blob[:200])
print(hashlib.sha256(blob).hexdigest())
```

Decision rule: if the required file is missing from the visible output inventory, rewrite it into the workspace root and re-run the audit.

## Bus number mapping

Power system bus numbers may not be contiguous. Always create a mapping from bus numbers to 0-indexed array positions:

```python
bus_num_to_idx = {int(buses[i, 0]): i for i in range(n_bus)}

f = bus_num_to_idx[int(branches[k, 0])]
t = bus_num_to_idx[int(branches[k, 1])]
```

## Susceptance matrix (B)

```python
import numpy as np

B = np.zeros((n_bus, n_bus))
for br in branches:
    f = bus_num_to_idx[int(br[0])]
    t = bus_num_to_idx[int(br[1])]
    x = float(br[3])
    if x == 0:
        continue
    b = 1.0 / x
    B[f, f] += b
    B[t, t] += b
    B[f, t] -= b
    B[t, f] -= b
```

## Line flows and loading

Convert per-unit flows to MW consistently, and compute loading from the same solved state used for any binding-line report.

```python
b = 1.0 / float(br[3])
flow_pu = b * (theta[f] - theta[t])
flow_MW = flow_pu * baseMVA

loading_pct = abs(flow_MW) / rating_MW * 100.0
```

Decision rule: if you change a constraint (e.g., counterfactual line limit), recompute flows/loading from the post-change solved `theta` and compare MW-to-MW.

## Common pitfalls

- Using `bus_id - 1` instead of an explicit `bus_num_to_idx` mapping for non-contiguous bus numbering.
- Mixing MW and per-unit in flow/limit calculations (e.g., comparing pu flow directly to an MW limit).
- Computing line loading or bindingness from `theta`/flows produced by a different solve than the one used to compute `binding_lines`/flags.