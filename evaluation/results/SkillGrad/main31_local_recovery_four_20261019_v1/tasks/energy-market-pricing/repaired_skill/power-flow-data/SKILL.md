---
name: power-flow-data
description: "Power system network data formats, topology, and unit conventions. Use when parsing bus/gen/branch arrays and interpreting ambiguous fields via metadata."
---

# Power Flow Data Guide

Network data often follows MATPOWER-like arrays plus extra fields. Correct modeling depends on using a **single coherent unit system** (MW or per-unit) and on consulting the file’s **schema/metadata** for any ambiguous field.

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

## Metadata-first unit audit (workflow)

Before using any *non-core* field (anything beyond the standard MATPOWER bus/gen/branch arrays), inspect the schema/metadata (often `column_info`, a data dictionary, or README) and record:
- unit (MW vs per-unit vs dollars)
- indexing (per-generator vs per-bus vs system-wide)
- time basis (per-hour vs per-interval)

```python
import json

with open("network.json") as f:
    data = json.load(f)

column_info = data.get("column_info", {})
print("Known top-level keys:", sorted(data.keys()))
print("Reserve metadata:", column_info.get("reserve_capacity"), column_info.get("reserve_requirement"))
```

Decision rule: if metadata is missing/unclear, infer units from magnitudes and then add assertions to catch wrong-scale values (e.g., per-unit values often have magnitude < 1).

Read references/unit-audit.md when you see fields with ambiguous units or a mix of MW and per-unit across arrays.
Skip when the schema explicitly states all fields are in MW and you never use per-unit.

## Choose one unit system and convert once

Pick either:
- **All MW** (simpler for reporting prices/flows), or
- **All per-unit** (closer to MATPOWER internals)

Then convert inputs exactly once at load time and keep the rest of the model consistent.

```python
baseMVA = float(data["baseMVA"])

Pd_MW = [float(b[2]) for b in data["bus"]]
Pd_pu = [p / baseMVA for p in Pd_MW]

# Example: convert a vector that might be MW or pu into MW (based on a flag).
vals = data["some_field"]
vals_MW = [v * baseMVA for v in vals] if field_is_pu else [float(v) for v in vals]
```

## Per-unit system reminder

```python
baseMVA = 100.0
P_pu = P_MW / baseMVA
P_MW = P_pu * baseMVA
```

## Bus number mapping

Power system bus numbers may not be contiguous. Always create a mapping:

```python
bus_num_to_idx = {int(buses[i][0]): i for i in range(n_bus)}
gen_bus = [bus_num_to_idx[int(g[0])] for g in gens]
```

## Common pitfalls

- Inferring units from one field but forgetting to convert a coupled field (e.g., converting `reserve_capacity` but not `reserve_requirement`).
- Computing derived metrics (line loading %, binding lines) from arrays produced by different solves or different unit systems.
