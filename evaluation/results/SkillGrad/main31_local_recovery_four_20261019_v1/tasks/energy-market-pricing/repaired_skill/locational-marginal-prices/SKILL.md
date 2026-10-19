---
name: locational-marginal-prices
description: "Extract locational marginal prices (LMPs) and reserve clearing prices from OPF dual values with correct sign and unit scaling."
---

# Locational Marginal Prices (LMPs)

LMPs are the marginal cost of serving one additional MW of load at each bus. In optimization terms, they come from **dual values** (shadow prices) of the nodal power balance constraints.

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

## Price extraction workflow: write the constraint, then rescale the dual

Before converting any dual to a reported price:

1. Confirm the solve is **optimal** (or an equivalent “converged, duals reliable” status for your solver).
2. Write down the exact priced constraint (algebra + direction) and annotate units (MW vs per-unit).
3. Convert the dual to $/MW (=$/MWh for a 1h period) using only that constraint definition.

```python
# Given a solved model, you should have stored the balance constraints.
# dual_val has units of ($/unit-of-constraint-LHS).

dual_val = balance_constraints[i].dual_value

# Example scaling template:
# - If balance is written in MW:   Pg_MW - Pd_MW == net_export_MW  -> price ≈ -dual_val ($/MW)
# - If balance is written in pu:   Pg_pu - Pd_pu == net_export_pu  -> price ≈ -dual_val / baseMVA ($/MW)

if balance_in_MW:
    lmp = -float(dual_val)
else:  # balance in per-unit
    lmp = -float(dual_val) / float(baseMVA)
```

Decision rule: if solver status is not optimal (e.g., `user_limit`, `inaccurate`, non-converged), do not report dual-based prices; re-solve with a solver/settings that provides stable duals or reformulate.

Read references/dual-price-units.md when reporting prices from duals and you did any per-unit scaling or introduced reserve constraints.
Skip when the model is entirely in MW and you have already validated sign/units with a marginal-cost check.

## Mandatory sanity checks (energy + reserve)

After computing prices, validate them against model-implied economics (not just “they look reasonable”):

```python
import numpy as np

lmp = np.asarray(lmp_by_bus, dtype=float)

# Plausibility: extreme magnitudes are a unit/sign red flag
assert np.all(np.isfinite(lmp)), "non-finite LMP"
assert np.max(np.abs(lmp)) < 1e4, "LMP magnitude suggests unit scaling error"

# Reserve MCP sign/units are defined by the exact reserve requirement constraint you wrote.
reserve_mcp = -float(reserve_con.dual_value) if reserve_con.dual_value is not None else 0.0
assert reserve_mcp >= -1e-6, "reserve MCP sign unexpected; re-check constraint direction/units"
```

Decision rule: if a computed price fails plausibility or sign checks, re-derive sign/scale from the written constraint form before changing the optimization.

## Finding binding lines

Lines at or near thermal limits (≥99% loading) cause congestion and LMP separation. See the `dc-power-flow` skill for line flow calculation details.

```python
BINDING_THRESHOLD = 99.0  # Percent loading

binding_lines = []
for k, br in enumerate(branches):
    f = bus_num_to_idx[int(br[0])]
    t = bus_num_to_idx[int(br[1])]
    x, rate = br[3], br[5]

    if x != 0 and rate > 0:
        b = 1.0 / x
        flow_MW = b * (theta.value[f] - theta.value[t]) * baseMVA
        loading_pct = abs(flow_MW) / rate * 100

        if loading_pct >= BINDING_THRESHOLD:
            binding_lines.append({
                "from": int(br[0]),
                "to": int(br[1]),
                "flow_MW": round(float(flow_MW), 2),
                "limit_MW": round(float(rate), 2)
            })
```

## Counterfactual analysis

When you modify a *specific* constraint (e.g., relax one line limit), validate the claim on that exact element, using the same flow/loading method used to build `binding_lines`.

1. Uniquely identify the target element (record its index/row and original limit)
2. Solve base case; for the target, record `flow_MW`, `loading_pct`, and `is_binding` from the same `theta` used for `binding_lines`
3. Apply the modification; re-solve counterfactual; record the same target-line quantities again
4. Define `congestion_relieved = was_binding_in_base and not binding_in_cf` using that same method

```python
# Invariants after solving both cases:
# - Relaxing a constraint cannot increase optimal cost.
assert cf_cost <= base_cost + 1e-6

# - If you claim congestion is relieved on the target, the target must disappear from binding_lines.
if congestion_relieved:
    assert target_in_binding_lines_cf is False
```

Decision rule: if the target-line check contradicts aggregate counts (e.g., binding line count increases while `congestion_relieved` is true), stop and recompute (a) target-line loading and (b) binding_lines from the same solved `theta` and MW limits before writing the report.

Read references/counterfactual-target-line-tracking.md when a counterfactual modifies a specific line/constraint and your report includes `congestion_relieved` or binding-line summaries.
Skip when you only report aggregate costs without any congestion/binding-line claims.

## Final report semantic validation (workflow)

Before writing/submitting `report.json`, run a cross-field validation pass (schema + invariants), especially after you “fix” one number like LMP scaling.

1. Validate required keys/types exist.
2. Validate numeric invariants (e.g., counterfactual cost nonincreasing).
3. Validate that any narrative/boolean claim is consistent with the numeric fields it summarizes.

```python
import json
from pathlib import Path

report = json.loads(Path("report.json").read_text())

base_cost = float(report["base"]["total_cost"])
cf_cost = float(report["counterfactual"]["total_cost"])
assert cf_cost <= base_cost + 1e-6

# Hard gate: never imply an empty binding-lines list unless it is empty.
cf_binding_lines = report["counterfactual"]["binding_lines"]
if isinstance(cf_binding_lines, list):
    assert (len(cf_binding_lines) == 0) or ("binding" not in report.get("notes", "").lower())
```

Decision rule: if you are about to write a sentence like “no binding lines remain” (or set a flag that implies it), assert `len(binding_lines)==0` under the same ≥99% definition; otherwise phrase precisely: “the target line is no longer binding; other binding constraints may remain.”

Read references/report-semantic-validation.md when the report combines counterfactual flags, binding-line summaries, and reserve MCPs.
Skip when the output is a single scalar/table with no cross-field semantics.

## Common pitfalls

- Extracting dual-based prices from a non-converged/inaccurate solve; duals may be meaningless.
- Rescaling duals without first writing the exact constraint form and units.
- Computing `congestion_relieved` from one flow/loading calculation path but `binding_lines` from another (units/solve-instance mismatch).
- Fixing one metric (e.g., LMP scaling) but not re-validating the full report schema and cross-field semantics.
- Conflating “target line relieved” with “system uncongested” and implying `binding_lines` is empty without checking its actual length.
