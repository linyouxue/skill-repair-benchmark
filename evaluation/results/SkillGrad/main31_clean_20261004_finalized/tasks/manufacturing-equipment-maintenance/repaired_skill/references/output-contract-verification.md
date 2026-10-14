# Output contract verification (multiple JSON deliverables)

Use this procedure when the evaluator expects multiple named output files (often JSON) and a partial/missing set is scored as a full failure.

## Procedure

1. **Define the contract early**: build a list of required outputs and the minimal top-level keys each must contain.
2. **Write first, then verify**: after writing all files, validate existence, JSON parseability, required keys, and that values are not accidentally empty/NaN.
3. **Fail fast**: if any check fails, correct writing/serialization and rerun verification before doing any further analysis.

```python
import json, math, os
from typing import Any


def is_bad_number(x: Any) -> bool:
    return isinstance(x, float) and (math.isnan(x) or math.isinf(x))


def verify_outputs(required_outputs: list[tuple[str, list[str]]]) -> None:
    for path, keys in required_outputs:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        missing = [k for k in keys if k not in obj]
        if missing:
            raise KeyError(f"{path} missing keys: {missing}")
        # Shallow content check: avoid silently writing NaN/Inf/null everywhere.
        for k in keys:
            v = obj.get(k)
            if v == "" or is_bad_number(v):
                raise ValueError(f"{path} has invalid value for key {k}: {v}")


# Branch 1: strict mode (recommended) — enforce all keys
strict = True
if strict:
    verify_outputs(required_outputs)
else:
    # Branch 2: exploratory mode — only check existence + JSON parse
    for path, _keys in required_outputs:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
```

## Verification step (and corrective action)

- If verification raises **FileNotFoundError**: fix the write paths and ensure you are writing into the evaluator-visible output directory; then rerun the full verification.
- If verification raises **JSONDecodeError**: fix serialization (write a proper JSON object, not a Python repr); then rerun verification.
- If verification raises **KeyError/ValueError**: fix schema/keys (or the upstream computation producing null/NaN); then rerun verification.
