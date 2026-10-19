# Report artifact semantic validation (JSON)

Use this right before final submission when the task requires producing a JSON report from an optimization result.

## Validate schema + units + invariants

1. Load the produced JSON.
2. Check required keys/types.
3. Check numeric units/scales (especially anything price-like or MW-like).
4. Check domain invariants implied by your optimization and by the prompt (e.g., counterfactual cost should not increase when a constraint is relaxed).

```python
import json
import math

REQUIRED_TOP_LEVEL = [
    # Fill/adjust per task family
    # "lmp_by_bus", "reserve_mcp", "binding_lines", "base_case", "counterfactual"
]

with open("report.json") as f:
    report = json.load(f)

for k in REQUIRED_TOP_LEVEL:
    if k not in report:
        raise KeyError(f"missing key: {k}")

# Example numeric checks
prices = []
for row in report.get("lmp_by_bus", []):
    p = float(row.get("lmp_dollars_per_MWh"))
    if not math.isfinite(p):
        raise ValueError("non-finite LMP")
    prices.append(p)

if prices and max(abs(p) for p in prices) > 1e4:
    raise ValueError("LMP scale too large; re-check dual scaling")

reserve_mcp = report.get("reserve_mcp_dollars_per_MWh")
if reserve_mcp is not None and float(reserve_mcp) < -1e-6:
    raise ValueError("reserve MCP negative; re-check constraint direction/sign")
```

## Runtime branch: a check fails

- If a **schema check** fails: re-read the task prompt, update the JSON structure, and rerun this validation.
- If a **unit/scale check** fails: do not patch the JSON numbers ad hoc; re-audit model units (read references/unit-audit.md) and re-derive price conversions (read references/dual-price-units.md), then regenerate the report.

## Verification step

Re-run this script after every change to:
- unit conversions
- price extraction logic
- report formatting

If it still fails, stop writing outputs and isolate the mismatch by printing the offending field, its source constraint/variable, and its units.
