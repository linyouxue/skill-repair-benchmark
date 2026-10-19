# Report semantic validation (counterfactual congestion + prices)

Use this checklist when producing a `report.json` (or similar artifact) that combines:
- base vs counterfactual solves,
- binding-lines lists/counts,
- congestion-relief booleans/claims,
- LMPs and/or reserve MCP.

The goal is to prevent **partial-fix tunnel vision**: after correcting one metric, ensure the full report is internally consistent.

## Procedure

### 1) Load and validate structure (types + required keys)

```python
import json
from pathlib import Path

required_top = {"base", "counterfactual"}
required_case = {"total_cost", "binding_lines"}

report = json.loads(Path("report.json").read_text())
assert required_top.issubset(report), f"missing top-level keys: {required_top - set(report)}"

for case in ["base", "counterfactual"]:
    obj = report[case]
    assert required_case.issubset(obj), f"missing keys in {case}: {required_case - set(obj)}"
    assert isinstance(obj["binding_lines"], list), f"{case}.binding_lines must be a list"
```

### 2) Numeric invariants (must hold for any relax-only counterfactual)

Branch on whether the counterfactual only relaxes constraints (uprates a line, increases a limit) vs changes costs/loads.

```python
base_cost = float(report["base"]["total_cost"])
cf_cost = float(report["counterfactual"]["total_cost"])

relax_only = bool(report.get("counterfactual", {}).get("relax_only", True))

if relax_only:
    assert cf_cost <= base_cost + 1e-6, "cf_cost should not exceed base_cost when only relaxing constraints"
else:
    # When loads/costs change, don't enforce monotonicity; instead ensure finiteness.
    assert cf_cost == cf_cost and abs(cf_cost) < 1e30
```

### 3) Binding-lines semantics vs narrative/flags

Branch on what you are about to claim:
- **System uncongested** means `binding_lines` should be empty (under the report’s definition).
- **Target line relieved** means only that the target line disappears; other lines may remain.

```python
def has_any_binding(case_obj):
    return len(case_obj["binding_lines"]) > 0

base_any = has_any_binding(report["base"])
cf_any = has_any_binding(report["counterfactual"])

claim_uncongested = bool(report.get("counterfactual", {}).get("system_uncongested", False))
claim_target_relieved = bool(report.get("counterfactual", {}).get("congestion_relieved", False))

if claim_uncongested:
    assert not cf_any, "system_uncongested implies counterfactual.binding_lines must be empty"

if claim_target_relieved and cf_any:
    # Allowed: other binding constraints may remain.
    pass

if (not claim_uncongested) and (not claim_target_relieved) and (not cf_any):
    # You may still be fine, but ensure narrative doesn't imply lingering congestion.
    pass
```

### 4) Target-line membership check (when applicable)

If the counterfactual modifies a particular line/constraint, validate the claim on that exact element.

```python
# Expected shape of a binding line entry: {"from": int, "to": int, ...}
# Use an order-invariant membership test.

target = report.get("counterfactual", {}).get("target_line")  # e.g., {"from": 1, "to": 2}

if target and report.get("counterfactual", {}).get("congestion_relieved") is True:
    cf_lines = report["counterfactual"]["binding_lines"]
    def matches_target(e):
        return {int(e.get("from")), int(e.get("to"))} == {int(target["from"]), int(target["to"])}

    assert not any(matches_target(e) for e in cf_lines), "target line still appears in counterfactual.binding_lines"
```

## Verification step (must prescribe corrective action)

1. If **structure checks** fail: rewrite `report.json` to include the missing keys/types; do not change the solver.
2. If **numeric invariants** fail:
   - Recompute `total_cost` from the same objective you solved (include all cost terms you report).
   - If the counterfactual only relaxed constraints but cost increased, re-check that you actually applied the relaxation and re-solved.
3. If **binding-lines vs claim** fails:
   - If `binding_lines` is non-empty, remove/flip any “system uncongested” claim and replace with “target line relieved; other binding constraints may remain.”
   - If you truly intended “system uncongested,” revisit the binding-line definition/threshold and recompute `binding_lines` from the final counterfactual solution.
4. If **target-line membership** fails: fix the target-line identification (row/index, from/to ordering), then recompute `binding_lines` and the `congestion_relieved` flag from the same flow/loading method.
