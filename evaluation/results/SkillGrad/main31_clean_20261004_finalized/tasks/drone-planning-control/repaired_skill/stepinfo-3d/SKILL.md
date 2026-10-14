---
name: stepinfo-3d
description: Compute 3D step-response metrics exactly as a reference spec and verify time-grid/indexing so saved metrics match the hidden evaluator.
---

# 3D Step-Response Metrics (stepinfo_3d)

## Workflow: spec-first metric compliance (not “reasonable engineering”)

1. Treat `metrics_3d.json` as **spec compliance**: do not invent alternative definitions for rise/settle/overshoot.
2. Use one canonical implementation for metric definitions; avoid “tuning with one definition, writing with another”.
3. Build `time_vec` from `sample_rate` and `max_iter`, and verify array/time alignment before computing metrics.
4. Compute metrics from **reloaded on-disk artifacts** (what the grader reads), not in-memory arrays.
5. Fail fast on any mismatch between the metrics you write and the metrics recomputed from the saved artifacts.

Read references/metric_spec_reload_crosscheck.md when you must write `metrics_3d.json` or when local gates pass but the benchmark fails.
Skip when metrics are computed by an imported reference evaluator you can call directly (and you store its outputs unchanged).

## When to Use

| Scenario | Metric to use |
|---|---|
| Pure z-step (hover, takeoff, land) | 1D `stepinfo` on `z` |
| Point-to-point flight with coupled axes | `stepinfo_3d` on Euclidean distance |
| Continuous path tracking (circle, figure-eight) | Neither — prefer RMS / integrated error |

1D metrics often mischaracterize diagonal flight because x/y/z corrections are coupled through tilt and thrust.

## Metrics Defined

| Metric | Definition (reference) |
|---|---|
| **Rise time** | First time distance to target ≤ 10% of initial distance |
| **Settling time** | Last time distance exceeds `settling_threshold × initial_distance` |
| **Overshoot %** | Max distance from target after first entering the settling band, as % of initial distance |
| **Steady-state error** | Final distance from target [m] |

## Implementation Logic

Given `pos_actual (3, n)`, `pos_target (3,)`, and `time_vec (n,)`:

1. Compute `dist[k] = ||pos_actual[:, k] − pos_target||₂`.
2. If `dist[0]` is ~0 (already at target), return zeros.
3. **Rise time**: first `time_vec[k]` with `dist[k] ≤ 0.1 * dist[0]`.
4. **Settling time**: scan backward for last `time_vec[k]` with `dist[k] > settling_threshold * dist[0]` (default `settling_threshold=0.02`).
5. **Overshoot**: after first entering the settling band, record `max(dist[k])` for the remaining samples and normalize by `dist[0]`.
6. **Steady-state error**: `dist[-1]`.

```python
import numpy as np

def stepinfo_3d(pos_actual: np.ndarray,
               pos_target: np.ndarray,
               time_vec: np.ndarray,
               settling_threshold: float = 0.02) -> dict:
    dist = np.linalg.norm(pos_actual - pos_target.reshape(3, 1), axis=0)
    d0 = float(dist[0])
    if d0 < 1e-6:
        return {"RiseTime": 0.0, "SettlingTime": 0.0, "Overshoot_pct": 0.0, "SteadyStateError": 0.0}

    rise_time = 0.0
    for k in range(dist.size):
        if dist[k] <= 0.1 * d0:
            rise_time = float(time_vec[k])
            break

    band = settling_threshold * d0
    settling_time = float(time_vec[-1])
    for k in range(dist.size - 1, -1, -1):
        if dist[k] > band:
            settling_time = float(time_vec[k])
            break

    entered = np.where(dist <= band)[0]
    if entered.size == 0:
        overshoot = 0.0
    else:
        overshoot = float(np.max(dist[entered[0]:]) / d0 * 100.0)

    return {
        "RiseTime": rise_time,
        "SettlingTime": settling_time,
        "Overshoot_pct": overshoot,
        "SteadyStateError": float(dist[-1]),
    }
```

## Common Pitfalls

- **Validator trap:** a gate script that recomputes metrics using the same non-reference logic that wrote the JSON can never detect mismatch versus the grader.
- **Time-grid mismatch:** `time_vec` and trajectory arrays must agree on length and indexing; an off-by-one at `max_iter` can silently change metrics.
- **Definition drift:** “rise time” and “settling time” conventions vary; do not assume textbook 10–90% or “first entry and stay” unless explicitly specified.
- **Schema drift:** ensure JSON keys and numeric types match what the grader expects; do not rename fields or omit required ones.
