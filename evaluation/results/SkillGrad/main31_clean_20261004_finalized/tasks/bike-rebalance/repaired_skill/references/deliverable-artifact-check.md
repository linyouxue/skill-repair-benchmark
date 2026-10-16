# Deliverable Artifact Check (Write → Re-open → Validate)

Use this procedure when the task is graded on a required output artifact (often a JSON/CSV file) and failures can occur even when the internal computation/model is correct.

Typical triggers:

- The prior attempt ended without writing the required file.
- The task demands a specific filename/path (e.g., `report.json`).
- The evaluator expects a schema with required keys, counts, and invariants.

## Procedure

### Step 1 — Write the artifact deterministically

Write to the exact expected path and prefer a single “write function” so you can re-run it.

```python
import json
from pathlib import Path

def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")

write_json(out_path, report_obj)
```

Runtime branch:

- If writing fails (permission/path error): write to a workspace path you control, then copy/move to the expected location.
- If you are unsure of the expected location: search for prior artifacts or follow the task statement’s explicit filename requirement.

### Step 2 — Re-open and validate basic parse + schema

```python
import json
from pathlib import Path

def load_json(path):
    return json.loads(Path(path).read_text())

obj = load_json(out_path)
required_top = ["summary", "vehicles", "stations"]
missing = [k for k in required_top if k not in obj]
assert not missing, f"missing top-level keys: {missing}"
```

Runtime branch:

- If JSON parsing fails: the file is corrupted/partial; re-write using an atomic write (write temp, then rename) and re-check.
- If keys are missing: you likely built the object from partial state; rebuild the full report object from the model/solution and re-write.

### Step 3 — Validate expected coverage (counts/IDs)

For any entity set that must be exhaustively reported (vehicles, stations, jobs), verify coverage.

```python
def assert_coverage(found_ids, expected_ids, label):
    missing = sorted(set(expected_ids) - set(found_ids))
    extra = sorted(set(found_ids) - set(expected_ids))
    assert not missing, f"{label} missing: {missing[:10]}"
    assert not extra, f"{label} extra: {extra[:10]}"

# example: vehicle IDs are 0..K-1
assert_coverage([v["id"] for v in obj["vehicles"]], list(range(K)), "vehicles")
assert_coverage([s["id"] for s in obj["stations"]], station_ids, "stations")
```

Runtime branch:

- If coverage fails: fix the report-building loop (iterate over the expected set, not over “visited” or “nonzero” items), then re-write.

### Step 4 — Validate core invariants

Pick 3–6 invariants that are cheap and strongly diagnostic.

```python
# example invariants (adapt to the task)
for v in obj["vehicles"]:
    route = v.get("route", [])
    assert route, "empty route"
    assert route[0] == "depot_start" and route[-1] == "depot_end", "bad depot endpoints"

# sums: stop-level quantities should match station rollups
station_net = {s["id"]: 0 for s in obj["stations"]}
for v in obj["vehicles"]:
    for stop in v.get("stops", []):
        station_net[int(stop["station_id"])] += int(stop["quantity"])

for s in obj["stations"]:
    sid = int(s["id"])
    assert int(s.get("net_change", 0)) == station_net[sid], "station rollup mismatch"
```

Runtime branch:

- If an invariant fails: do not proceed to “tuning” the solver objective. First locate whether the bug is (a) extraction from the solver, (b) the semantics/sign convention, or (c) the report aggregation logic; fix, then re-run steps 1–4.

## Verification (must pass before ending)

Verification check:

1. The output file exists at the required path.
2. It parses cleanly.
3. Required keys exist.
4. Expected entity coverage checks pass.
5. Invariant checks pass.

If any verification check fails: **continue working** (rebuild report object, fix extraction/aggregation, re-write), and re-run the verification until it passes.
