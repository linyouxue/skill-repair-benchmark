# Metric spec reload crosscheck (prevent “validator trap”)

Use this procedure when you must write a metrics JSON that a hidden evaluator will grade, and you suspect that local gates could pass while the benchmark fails.

## Goal

Ensure the metrics you write are **exactly** what you would recompute from the saved artifacts using the **same canonical metric implementation**. This prevents a self-consistency trap where you validate against your own non-reference metric definitions.

## Procedure

### 1) Adopt one canonical implementation

- Pick one metric function as canonical for the deliverable (e.g., `stepinfo_3d`).
- Do not tune with one definition and write with another.

### 2) Write artifacts first, then reload

Compute and save all graded artifacts (e.g., `planned_trajectory.npy`, `actual_trajectory.npy`) and then *reload them from disk* before computing metrics.

```python
import json
import numpy as np
from pathlib import Path

# canonical import
from stepinfo_3d import stepinfo_3d

def load_traj(out_dir: str):
    out = Path(out_dir)
    planned = np.load(out / "planned_trajectory.npy")
    actual = np.load(out / "actual_trajectory.npy")
    return planned, actual
```

### 3) Rebuild and verify the time grid

Use `sample_rate` and `max_iter` to define the time vector, and enforce alignment with the loaded arrays.

```python
def build_time_vec(sample_rate: float, max_iter: int):
    n = int(max_iter)
    t = np.arange(n, dtype=float) / float(sample_rate)
    return t

planned, actual = load_traj(out_dir)
max_iter = planned.shape[1]

# Branch: if shapes disagree, fix alignment before any metric computation.
if actual.shape[1] != max_iter:
    raise ValueError("planned/actual horizon mismatch; fix saving or truncation logic")

time_vec = build_time_vec(sample_rate, max_iter)
if time_vec.size != max_iter:
    raise ValueError("time_vec length mismatch; fix max_iter/sample_rate usage")
```

### 4) Compute metrics from the reloaded artifacts

Define the target consistently with the planner’s final waypoint / terminal desired position, and compute metrics from the loaded data.

```python
pos_actual = actual[0:3, :]
pos_target = planned[0:3, -1]
metrics_ref = stepinfo_3d(pos_actual, pos_target, time_vec)
```

### 5) Compare against the JSON you plan to write (or already wrote)

- If you already wrote `metrics_3d.json`, reload it and compare numbers.
- If you have not written it yet, compare against the dict you are about to serialize.

```python
def max_abs_diff(d1: dict, d2: dict):
    keys = sorted(set(d1) | set(d2))
    diffs = []
    for k in keys:
        if k not in d1 or k not in d2:
            return float("inf")
        diffs.append(abs(float(d1[k]) - float(d2[k])))
    return max(diffs) if diffs else 0.0

metrics_path = Path(out_dir) / "metrics_3d.json"
if metrics_path.exists():
    metrics_disk = json.loads(metrics_path.read_text())
    d = max_abs_diff(metrics_ref, metrics_disk)
    if d > 1e-9:
        raise AssertionError(f"metrics mismatch vs reload+reference (max abs diff {d})")
else:
    metrics_to_write = metrics_ref
    metrics_path.write_text(json.dumps(metrics_to_write, indent=2))
```

## Verification

- **Pass condition:**
  - `planned.shape[1] == actual.shape[1] == len(time_vec)`
  - `max_abs_diff(metrics_ref, metrics_disk) <= 1e-9`

- **On failure (next action):**
  1. If horizons/time grid mismatch, fix your save/truncation/padding logic so both trajectories share the exact `max_iter` and rebuild `time_vec` from that same `max_iter`.
  2. If metrics mismatch, delete the custom metric implementation and call the canonical reference function directly; regenerate `metrics_3d.json` from reloaded artifacts only.
  3. Re-run this procedure on a single case before batch-running all outputs.
