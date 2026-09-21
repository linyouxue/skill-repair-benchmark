# Required artifact: /root/answers.json

Use this checklist when the task mandates a JSON artifact at a fixed path (commonly `/root/answers.json`) with specific top-level keys (for example `q1_answer`, `q2_answer`, ...).

## Procedure

### 1) Determine schema from instructions
- Extract the exact required path.
- Extract the required top-level keys and whether values must be strings, numbers, arrays, or objects.

### 2) Write the file exactly once (branch on key uncertainty)

```python
import json
from pathlib import Path

def build_payload(required_keys, value_by_key):
    payload = {}
    for k in required_keys:
        if k in value_by_key:
            payload[k] = value_by_key[k]
        else:
            # Branch A: you do not have the answer yet -> fill placeholder and revisit
            payload[k] = None
    return payload

def write_answers_json(path, payload):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return p
```

Runtime branch:
- If any value is `None`, do not finalize: compute the missing answers, update the payload, and rewrite the file.
- If all values are present, proceed to verification.

### 3) Verification (parse + key set + corrective action)

```python
import json

def verify_answers_json(path, required_keys):
    data = json.loads(open(path, "r", encoding="utf-8").read())
    missing = sorted(set(required_keys) - set(data))
    extra = sorted(set(data) - set(required_keys))
    if missing or extra:
        raise AssertionError({"missing": missing, "extra": extra})
    return data
```

If verification fails:
1. Re-read the task instructions and correct the required key set (common failure: wrong numbering or naming).
2. Rewrite the JSON with exactly the required keys.
3. Re-run verification until it passes.

### 4) Final existence check
- Confirm the file exists at the exact path (not a relative path with the same name).
- Only then terminate.
