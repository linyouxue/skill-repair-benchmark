# Output artifact protocol (/app/output/*.json)

Use this chapter when the task is graded by the presence and schema of multiple JSON deliverables (e.g., `q01.json`…`qNN.json`) rather than a single free-form response.

## Procedure

### 1) Derive the contract

- List every required output filename and its expected top-level JSON type (object vs list).
- For each file, list required keys, allowed nullability, and any sorting/rounding rules.
- Decide what to emit when upstream data is missing (typically `null`, empty lists, and/or an `errors` field if allowed by the schema).

### 2) Write deterministically (always create every file)

```python
import json
from pathlib import Path

def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

out_dir = Path("/app/output")

# Branch: schema expects dict vs list
schema_type = "dict"  # or "list"
if schema_type == "dict":
    payload = {"answer": None, "details": []}
else:
    payload = []

write_json(out_dir / "q01.json", payload)
```

### 3) Verify and correct (pre-termination)

Verification must include existence + parse + schema.

```python
import json
from pathlib import Path

def validate_required_files(out_dir: Path, required: dict):
    """required: name -> callable(payload)->bool (schema check)."""
    problems = []
    for name, check in required.items():
        p = out_dir / name
        if not p.exists() or p.stat().st_size == 0:
            problems.append((name, "missing_or_empty"))
            continue
        try:
            payload = json.loads(p.read_text())
        except Exception:
            problems.append((name, "invalid_json"))
            continue
        if check is not None and not check(payload):
            problems.append((name, "schema_mismatch"))
    return problems

out_dir = Path("/app/output")
required = {
    "q01.json": lambda d: isinstance(d, dict) and "answer" in d,
    "q02.json": lambda d: isinstance(d, dict),
}

problems = validate_required_files(out_dir, required)
if problems:
    # Corrective action: (1) re-read spec to fix schema, (2) re-materialize defaults,
    # (3) re-run validation; do not continue analysis until clean.
    raise RuntimeError(f"Output validation failed: {problems}")
```

## Runtime branches to handle common grading constraints

- If the grader expects stable ordering: sort arrays of objects by their key fields before writing.
- If numeric formatting matters: round to the specified precision right before serialization.
- If some data is missing: still write the file; fill missing fields with `null`/empty arrays per contract, then record what was missing in an allowed field.

## Verification step (with next action)

- **Check fails (missing/invalid/schema mismatch):** re-read the task spec, update the payload shape (keys/types/nullability), rewrite the file(s), and re-run validation until `problems == []`.
- **Check passes:** proceed to terminate.
