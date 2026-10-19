# Report semantic validation (market + network outputs)

Use this right before writing/submitting `report.json` when the report combines multiple derived outputs (prices, binding lines, counterfactual flags, reserve MCP/cost components).

## Checklist

### 1) Validate required keys + types

```python
import json
from pathlib import Path

report = json.loads(Path("report.json").read_text())

required = {
    "base": dict,
    "counterfactual": dict,
}

for k, typ in required.items():
    if k not in report:
        raise KeyError(f"missing key: {k}")
    if not isinstance(report[k], typ):
        raise TypeError(f"{k} must be {typ.__name__}")
```

Runtime branch:
- If your task defines a stricter schema (exact keys), replace `required` with that schema and fail fast.

### 2) Cross-field economic/physical invariants

```python
# Example: cost monotonicity for a relaxation counterfactual
base_cost = float(report["base"]["total_cost"])
cf_cost = float(report["counterfactual"]["total_cost"])

if cf_cost > base_cost + 1e-6:
    raise AssertionError("counterfactual cost increased under relaxation; re-check objective/optimality")

# Example: congestion flag must agree with target-line bindingness if both are reported
if "congestion_relieved" in report.get("counterfactual", {}):
    flag = bool(report["counterfactual"]["congestion_relieved"])
    has_target = ("target_line" in report["counterfactual"])
    if has_target:
        was_binding = bool(report["base"]["target_line"]["binding"])
        is_binding = bool(report["counterfactual"]["target_line"]["binding"])
        if flag != (was_binding and (not is_binding)):
            raise AssertionError("congestion_relieved contradicts target_line binding fields")
```

Runtime branch:
- If the report does not include explicit `target_line` fields, validate against the binding-line lists: ensure the target line appears in `base.binding_lines` and is absent from `counterfactual.binding_lines` when `congestion_relieved` is true.

### 3) Price semantics (dual-based outputs)

```python
base = report["base"]

# Reserve MCP semantics must match whether reserve is priced.
if "reserve_mcp" in base:
    mcp = float(base["reserve_mcp"])
    priced = bool(base.get("reserve_priced", False))

    if priced and mcp <= 1e-9:
        raise AssertionError("reserve_priced=true but reserve_mcp is ~0; check reserve offers/cost term")

    if (not priced) and base.get("reserve_offer_data_present", False):
        raise AssertionError("reserve offer data present but reserve_priced=false; reconcile interpretation")
```

## Verification (what to do when it fails)

- If schema/type checks fail → fix the writer (keys, nesting, numeric types) and rewrite `report.json`.
- If invariants fail (cost monotonicity, congestion flag contradictions) → recompute the underlying quantities from the solved model (same theta/units) before editing the JSON.
- If price semantics fail → re-audit reserve offers + dual units/sign and re-solve with a solver that returns reliable duals.
