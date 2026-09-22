---
name: reflow-machine-maintenance-guidance
description: Provide reflow machine maintenance guidance by deriving limits from handbooks, computing metrics from MES/thermocouple/defect data, and cross-validating results.
---

This skill should be considered when you need to answer reflow equipment maintenance questions based on thermocouple data, MES data, defect data, and reflow technical handbooks.

## Plan the run (contract-first)

1. Identify the required deliverables (exact filenames, directory, and JSON schema) from the task spec.
2. Create placeholder JSONs (or in-memory payloads) for **every** required deliverable immediately, so “no data” cases still yield files.
3. Decide which metrics must be computed from handbook limits vs. computed from datasets; treat handbook as normative when conflicts exist.
4. Only terminate after re-running a strict “write + validate outputs” gate over all required artifacts.

## Write required output artifacts (blocking pre-termination gate)

Treat output writing/validation as a **hard gate** that runs twice:
- **Early:** create every required file as a placeholder.
- **Late (immediately before `end_turn`):** overwrite placeholders with final answers and re-validate.

If the gate fails, do not terminate: fix payloads and re-run the gate until clean.

```python
import json
from pathlib import Path

out_dir = Path("/app/output")
out_dir.mkdir(parents=True, exist_ok=True)

required = {
    "q01.json": {"answer": None},
    "q02.json": {"answer": None},
}

# 1) Early: write placeholders for ALL required deliverables.
for name, payload in required.items():
    (out_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

# 2) Late: immediately before end_turn, re-run the same gate over ALL required files.
problems = []
for name in required:
    p = out_dir / name
    if (not p.exists()) or p.stat().st_size == 0:
        problems.append((name, "missing_or_empty"))
        continue
    try:
        json.loads(p.read_text())
    except Exception:
        problems.append((name, "invalid_json"))

if problems:
    raise RuntimeError(f"Output gate failed; rewrite + re-check before ending: {problems}")
```

Decision rule: if the task requires multiple `/app/output/*.json` deliverables, **never** call `end_turn` until the late gate passes for every required file (existence + non-empty + JSON-parse + schema/format rules when specified).

Read references/output-artifact-protocol.md when the task specifies multiple `/app/output/*.json` deliverables or strict schema/formatting constraints. Skip when the environment returns a single free-form answer.

## Extract handbook constraints into a config

First retrieve related info from the handbook and corresponding datasets. Most frequently asked concepts include preheat, soak, reflow, cooling, ramp, slope, C/s, liquidus and wetting time, ramp rate guidance, time above liquidus, TAL, peak temperature guidance, minimum peak, margin above liquidus, conveyor speed, dwell time, heated length, zone length, time-in-oven, thermocouple placement, cold spot, worst case, representative sensor, numeric limits, temperature regions.

If the handbook provides multiple values or constraints, implement all and use the stricter constraint or the proper value.

```python
cfg = {
    # region selectors: {"type":"temp_band","tmin":...,"tmax":...}
    # or {"type":"zone_band","zones":[...]}
    # or {"type":"time_band","t_start_s":...,"t_end_s":...}
    "region": None,
    "ramp_limit_c_per_s": None,
    "tal_threshold_c": None,
    "tal_min_s": None,
    "tal_max_s": None,
    "peak_margin_c": None,
}
```

## Load and normalize MES + thermocouple data

Normalize key columns and sort deterministically before any metric computation.

```python
import os
import pandas as pd

runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))

for c in ["run_id"]:
    runs[c] = runs[c].astype(str)
    tc[c] = tc[c].astype(str)
tc["tc_id"] = tc["tc_id"].astype(str)

tc = tc.sort_values(["run_id", "tc_id", "time_s"], kind="mergesort")
```

Decision rule: if `time_s` is not strictly increasing within a thermocouple trace, ignore segments with `dt <= 0` rather than extrapolating.

## Compute ramp / slope metrics (segment-based)

Compute slopes per segment `s_i = (T_i - T_{i-1}) / (t_i - t_{i-1})` for `dt > 0`, then aggregate (e.g., max ramp) over the chosen region.

```python
import numpy as np

def max_slope(df_tc):
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(float)
    y = g["temp_c"].to_numpy(float)
    best = None
    for i in range(1, len(g)):
        dt = t[i] - t[i-1]
        if dt <= 0:
            continue
        s = (y[i] - y[i-1]) / dt
        best = s if best is None else max(best, s)
    return best
```

Read references/region-filtering.md when the slope/ramp must be computed only within a temperature band, a zone subset, or a time window. Skip when the metric is over the full trace.

## Compute TAL / wetting time (threshold crossing)

For wetting/TAL-type metrics, compute time above a threshold using segment interpolation (handle partial crossings).

```python

def time_above(df_tc, thr):
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(float)
    y = g["temp_c"].to_numpy(float)
    total = 0.0
    for i in range(1, len(g)):
        t0, t1 = t[i-1], t[i]
        y0, y1 = y[i-1], y[i]
        if t1 <= t0:
            continue
        if y0 > thr and y1 > thr:
            total += (t1 - t0)
        elif (y0 <= thr < y1) or (y1 <= thr < y0):
            frac = (thr - y0) / (y1 - y0) if y1 != y0 else None
            if frac is not None:
                tcross = t0 + frac * (t1 - t0)
                total += (t1 - tcross) if y1 > thr else (tcross - t0)
    return total
```

## Peak, min-peak, and run-level reductions

For each TC, `peak_tc = max(temp_c)`. For a run, `min_peak_run = min(peak_tc)` and `required_peak = liquidus + peak_margin`.

When reducing multiple thermocouples to one run-level result:
- If selecting a maximum metric, choose `(max_value, smallest_tc_id)`.
- If selecting a minimum metric, choose `(min_value, smallest_tc_id)`.

```python

def reduce_by_min_tc(values):
    # values: list of (tc_id, metric)
    return min(((m, tc) for tc, m in values if m is not None), default=(None, None))
```

## Conveyor speed feasibility from heated length and dwell/time-in-oven

Given effective heated length `L_eff_cm`:
- With minimum dwell `t_min_s`: `speed_max_cm_min = (L_eff_cm / t_min_s) * 60`.
- With maximum time `t_max_s`: `speed_min_cm_min = (L_eff_cm / t_max_s) * 60`.

```python

def speed_bounds_cm_min(L_eff_cm, t_min_s=None, t_max_s=None):
    s_min = (L_eff_cm / t_max_s) * 60 if t_max_s else None
    s_max = (L_eff_cm / t_min_s) * 60 if t_min_s else None
    return s_min, s_max
```

## Common Pitfalls

- Ending a run without writing and validating the required `/app/output/*.json` artifacts; run an early placeholder write and a late pre-termination output gate (existence + parse + schema).
- Computing thermocouple metrics on unsorted samples or with non-increasing timestamps; always sort and ignore `dt <= 0` segments.
- Applying only one of multiple handbook constraints (or not choosing the stricter one) when the spec requires satisfying all limits.
