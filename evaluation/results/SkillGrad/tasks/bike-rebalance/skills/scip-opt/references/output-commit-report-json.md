# Output Commit: Write `report.json` (or other required JSON deliverable)

Use this procedure when the evaluator expects a specific JSON file artifact on disk at the end of the run (common names: `report.json`, `solution.json`, `answer.json`). Missing the file is an earliest-failure class: the grader cannot evaluate feasibility or objective.

## Procedure

1. **Assemble the full payload** in memory.
   - Include every required top-level key.
   - Include every required per-entity record (e.g., all vehicles, all stations), even if some are “empty”.

2. **Run pre-write completeness checks**.

3. **Write atomically-ish** (write, then read back).

4. **Run post-write checks** on the parsed file contents.

## Runnable Python scaffold (with branches)

```python
import json
from pathlib import Path

def write_json(path: str, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True))


def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text())


def validate_required_keys(obj: dict, required_keys: list[str]) -> None:
    missing = [k for k in required_keys if k not in obj]
    if missing:
        raise ValueError(f"missing required keys: {missing}")


def validate_entities_cover_all(obj_list: list[dict], id_key: str, expected_ids: list) -> None:
    got = [row.get(id_key) for row in obj_list]
    missing = [i for i in expected_ids if i not in set(got)]
    if missing:
        raise ValueError(f"missing entities for ids: {missing}")


# Inputs you should already have at the end of solving
payload = report_obj              # dict
required_keys = required_top_keys # list[str]

# Branch A: entities are lists of dicts with explicit IDs
if "vehicles" in payload and isinstance(payload.get("vehicles"), list):
    validate_entities_cover_all(payload["vehicles"], id_key="id", expected_ids=expected_vehicle_ids)

# Branch B: entities are a dict keyed by ID
elif "vehicles" in payload and isinstance(payload.get("vehicles"), dict):
    got_ids = [int(k) for k in payload["vehicles"].keys()]
    missing = [i for i in expected_vehicle_ids if i not in set(got_ids)]
    if missing:
        raise ValueError(f"missing vehicles: {missing}")

# Branch C: no vehicles concept
else:
    pass

validate_required_keys(payload, required_keys)

# Commit
out_path = "report.json"
write_json(out_path, payload)

# Verification: read back and re-validate
loaded = read_json(out_path)
validate_required_keys(loaded, required_keys)
assert Path(out_path).exists(), "output file not found after write"
```

## Verification and corrective action

- If the **file does not exist** after write: re-check the working directory, permissions, and the exact filename expected by the grader; then re-run the write step with an absolute or confirmed relative path.
- If **JSON parsing fails**: the payload contains non-JSON-serializable objects (e.g., numpy types); convert them to Python `int`/`float`/`str` and re-run the write + readback.
- If **required keys/entities are missing**: fix the report assembly step to always emit empty/default records for unassigned vehicles/stations, then re-run pre-write checks and commit again.
- If **post-write checks disagree** with pre-write checks: you are mutating the payload between validation and write; freeze it (deepcopy) before writing, then re-run.
