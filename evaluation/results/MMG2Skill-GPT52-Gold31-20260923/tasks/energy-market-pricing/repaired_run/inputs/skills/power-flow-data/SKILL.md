---
name: power-flow-data
description: Load MATPOWER-format network data from `network.json` efficiently (including
  reserves) and do quick sanity checks; set up a virtualenv if required packages are
  missing.
---

## Steps
1. Confirm the input snapshot exists at `./network.json`.
2. If imports fail due to an externally managed environment, create and use a local virtualenv:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   pip install numpy cvxpy clarabel
   ```
3. Load the JSON with Python (avoid line-by-line shell inspection for large files):
   ```python
   import json, numpy as np
   with open("network.json") as f:
       data = json.load(f)
   baseMVA = float(data["baseMVA"])
   buses = np.array(data["bus"])
   gens = np.array(data["gen"])
   branches = np.array(data["branch"])
   gencost = np.array(data["gencost"])
   reserve_capacity = np.array(data["reserve_capacity"])
   reserve_requirement = float(data["reserve_requirement"])
   ```
4. Print quick sanity checks (counts/shapes and reserve requirement):
   ```python
   print(buses.shape, gens.shape, branches.shape, gencost.shape)
   print("reserve_requirement:", reserve_requirement)
   ```
## Expected Result
All MATPOWER arrays and reserve fields loaded into NumPy with correct dimensions, ready for DC-OPF and dual-based pricing.
