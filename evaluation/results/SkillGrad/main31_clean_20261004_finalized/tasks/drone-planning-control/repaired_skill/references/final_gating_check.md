# Final gating check on saved drone-planning artifacts

Use this checklist when the task has **hard numeric thresholds** and grading reads **on-disk artifacts** (e.g., `/root/results/<id>/planned_trajectory.npy` and per-command metrics JSON). The goal is to prevent reporting stale numbers from memory or from an earlier run.

## Procedure

### 1) Discover result directories and required files

```python
import json
import os
from glob import glob
import numpy as np

REQ = ["planned_trajectory.npy", "metrics_3d.json"]

result_dirs = sorted([d for d in glob("/root/results/*") if os.path.isdir(d)])
missing = []
for d in result_dirs:
    for f in REQ:
        p = os.path.join(d, f)
        if not os.path.exists(p):
            missing.append(p)

if missing:
    raise FileNotFoundError("Missing required outputs:\n" + "\n".join(missing))
print(f"Found {len(result_dirs)} result dirs with required files")
```

### 2) Load metrics from disk and check thresholds (branching)

```python
THRESH = {
    "max_per_timestep_pos_err": 0.05,
    "SteadyStateError": 0.05,
}

failures = []

for d in result_dirs:
    cmd_id = os.path.basename(d)

    # Branch A: metrics json exists and can be parsed
    try:
        with open(os.path.join(d, "metrics_3d.json"), "r") as f:
            metrics = json.load(f)
    except Exception as e:
        failures.append((cmd_id, "metrics_3d.json unreadable", str(e)))
        continue

    # Branch B: check steady-state threshold if present
    sse = metrics.get("SteadyStateError", None)
    if isinstance(sse, (int, float)) and sse > THRESH["SteadyStateError"]:
        failures.append((cmd_id, "SteadyStateError", sse))

    # Optional: if your checker stores max error under any key, check it.
    for k in ["MaxError", "max_error", "max_per_step_error", "max_per_timestep_pos_err"]:
        v = metrics.get(k, None)
        if isinstance(v, (int, float)) and v > THRESH["max_per_timestep_pos_err"]:
            failures.append((cmd_id, k, v))
            break

print("FAILURES:")
for f in failures:
    print("  ", f)
```

### 3) Verification + corrective action

- **Pass condition:** `len(failures) == 0` and no required files are missing.
- **If fail:**
  1. Do **not** report “all pass”. Instead, print the failing command IDs and which metric(s) exceed thresholds.
  2. Re-run the planner/controller for those command IDs, overwrite their on-disk artifacts, and then **repeat steps 1–3**.

A common failure mode is to tweak code but forget to regenerate outputs for every command; this procedure catches that.

## Notes

- This chapter focuses on the *final gating step*; it does not prescribe the physics/controller fix.
- If the metric file does not contain max per-timestep error, call the project-provided checker script/function to compute it from the saved trajectory and simulation logs, then store it in `metrics_3d.json`.
