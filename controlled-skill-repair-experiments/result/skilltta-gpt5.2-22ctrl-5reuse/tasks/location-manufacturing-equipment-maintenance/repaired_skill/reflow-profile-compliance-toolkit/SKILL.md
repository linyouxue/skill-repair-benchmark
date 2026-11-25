---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval and thermocouple computations for reflow profile compliance outputs such as ramp, TAL, peak, feasibility, and selection.
---

When to invoke
1. Whenever the task involves reflow-related questions from thermocouple data, MES data, defect data, and handbook-defined regions/windows/limits.
2. When you must extract numeric limits / temperature regions / timing windows / margins / feasibility rules from handbook.pdf (no guessing).
3. When you must compute run-level metrics from time–temperature thermocouple traces deterministically (stable tie-breaks, stable sorting).

Core principles
- Handbook-first: definitions, regions/windows, limits, and “representative thermocouple” rules must come from the handbook.
- Deterministic: if multiple thermocouples or multiple ways to compute a metric exist, use a documented, stable rule.
- Non-hallucinatory: if a parameter cannot be found in the handbook or cannot be mapped to the available data fields, output null and avoid claiming compliance.


## A) Trial deliverables & completion conditions (only when the task explicitly requests these artifacts)

If the task prompt requests writing Q01–Q05 outputs, you must create EXACTLY these files under `/app/output/`:
- `/app/output/q01.json`
- `/app/output/q02.json`
- `/app/output/q03.json`
- `/app/output/q04.json`
- `/app/output/q05.json`

Global formatting rules
- Round all float values to 2 decimals at serialization time.
- Arrays must be sorted ascending by the specified key (run_id / board_family / board_id).
- Dicts keyed by IDs must be emitted in ascending key order.
- Use JSON `null` for missing/uncomputable values; do not emit NaN/Inf.

Required schemas (must match the prompt)

Q01 `/app/output/q01.json`
```json
{
  "ramp_rate_limit_c_per_s": 0.0,
  "violating_runs": ["R0000"],
  "max_ramp_by_run": {
    "R0000": {
      "tc_id": "TC1",
      "max_preheat_ramp_c_per_s": 0.0
    }
  }
}
```

Q02 `/app/output/q02.json`
```json
[
  {
    "run_id": "R0000",
    "tc_id": "TC1",
    "tal_s": 0.0,
    "required_min_tal_s": 0.0,
    "required_max_tal_s": 0.0,
    "status": "compliant"
  }
]
```

Q03 `/app/output/q03.json`
```json
{
  "failing_runs": ["R0000"],
  "min_peak_by_run": {
    "R0000": {
      "tc_id": "TC1",
      "peak_temp_c": 0.0,
      "required_min_peak_c": 0.0
    }
  }
}
```

Q04 `/app/output/q04.json`
```json
[
  {
    "run_id": "R0000",
    "required_min_speed_cm_min": 0.0,
    "actual_speed_cm_min": 0.0,
    "meets": true
  }
]
```

Q05 `/app/output/q05.json`
```json
[
  {
    "board_family": "FAM_A",
    "best_run_id": "R0000",
    "runner_up_run_ids": ["R0001"]
  }
]
```


## B) Handbook “where to look” checklist

Search the handbook for these common sections/tables:
- Thermal profile overview: defines “preheat”, “soak”, “reflow”, “cooling”.
- Ramp rate guidance: “ramp”, “slope”, “°C/s”, “C/s”.
- Liquidus & wetting time: “liquidus”, “time above liquidus”, “TAL”, “wetting”.
- Peak temperature guidance: “peak”, “minimum peak”, “margin above liquidus”.
- Conveyor / dwell feasibility: “conveyor speed”, “dwell time”, “heated length”, “zone length”, “time-in-oven”.
- Thermocouple placement: “cold spot”, “worst case”, “representative sensor”.

Extract a compact config object from the handbook and use it for all computations:

```python
cfg = {
  # Q01
  "preheat_definition": "...quoted/parsed text...",
  "preheat_region": {  # temp_band OR time_band OR zone_band
    "type": "temp_band",
    "tmin": None,
    "tmax": None
  },
  "ramp_limit_c_per_s": None,

  # Q02
  "liquidus_c": None,                 # handbook-defined value OR handbook-instructed source
  "tal_window_definition": "...",
  "tal_min_s": None,
  "tal_max_s": None,

  # Q03
  "required_min_peak_c": None,        # or derived per handbook (e.g., liquidus + margin)

  # Q04
  "conveyor_rule": {"type": "..."},

  # Representative TC selection rules
  "rep_tc_rules": {
     "ramp": "...",
     "tal": "...",
     "peak": "..."
  }
}
```

If multiple applicable constraints exist, implement all and use the stricter one (record which one you used in code comments/logs; do not hard-code numbers into the skill text).


## C) Deterministic thermocouple computation recipes

### C1. Sorting and de-dup rules
Always sort samples by time before any computation:
```python
DF_TC = DF_TC.sort_values(["run_id", "tc_id", "time_s"], kind="mergesort")
```
Ignore segments where `dt <= 0` (non-monotonic timestamps).

### C2. Segment slope (ramp rate)
Finite-difference slope on consecutive samples:
- `s_i = (T_i - T_{i-1}) / (t_i - t_{i-1})` for `dt > 0`
- “max ramp” is `max(s_i)` over the region.

Region filtering patterns:
- Temperature band region: only include segments where **both endpoints** satisfy `tmin <= T <= tmax`.
- Zone band region: filter by `zone_id in zones`.
- Time band region: filter by `t_start_s <= time_s <= t_end_s`.

Robust implementation (temperature-band example):
```python
def max_slope_in_temp_band(df_tc, tmin, tmax):
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    best = None
    for i in range(1, len(g)):
        dt = t[i] - t[i-1]
        if dt <= 0:
            continue
        if (tmin <= y[i-1] <= tmax) and (tmin <= y[i] <= tmax):
            s = (y[i] - y[i-1]) / dt
            best = s if best is None else max(best, s)
    return best  # None if no valid segments
```

### C3. Time above threshold with linear interpolation (“integral” definition)
If the handbook defines TAL/wetting as “total time above liquidus/threshold”, compute it by summing time above threshold across all segments with interpolation:

```python
def time_above_threshold_s(df_tc, thr):
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    total = 0.0
    for i in range(1, len(g)):
        t0, t1 = t[i-1], t[i]
        y0, y1 = y[i-1], y[i]
        if t1 <= t0:
            continue

        # fully above
        if y0 > thr and y1 > thr:
            total += (t1 - t0)
            continue

        # crossing: interpolate crossing time
        crosses = (y0 <= thr < y1) or (y1 <= thr < y0)
        if crosses and (y1 != y0):
            frac = (thr - y0) / (y1 - y0)
            tcross = t0 + frac * (t1 - t0)
            if y0 <= thr and y1 > thr:
                total += (t1 - tcross)
            else:
                total += (tcross - t0)
    return total
```

### C4. TAL window alternative (“first-up to last-down” definition)
If (and only if) the handbook explicitly defines TAL as “time from first crossing above liquidus on the rising edge to the last crossing below liquidus on the falling edge”, compute:
- `tal_s = t_down_last - t_up_first`
using linear interpolation for crossing times.

Important: This “span” definition is not always equivalent to “total time above” if the trace dips below liquidus multiple times due to noise/oscillation. Always follow the handbook’s wording.


## D) Representative thermocouple selection (handbook-first, deterministic fallback)

The prompt may require a single `tc_id` per run, but handbooks may require “all points must meet spec” or may name a specific TC location.

### D1. Implement the handbook rule literally
Search for and follow explicit instructions such as:
- “Use the thermocouple at [specified location] for acceptance.”
- “Use the coldest thermocouple / worst-case location.”
- “Acceptance is based on the minimum peak across all thermocouples.”

If the handbook requires checking all TCs for pass/fail, you MUST still compute pass/fail correctly internally; when forced to output a single `tc_id`, output the TC that drives the run-level decision (e.g., the violating TC, or the most limiting TC).

### D2. Deterministic fallback when the handbook is silent about a single representative TC
Use a conservative, compliance-driven rule that avoids false passes.

1) Compute the metric per TC and compare to the applicable limit(s).

2) If any TC is non-compliant, select the TC with the **largest violation magnitude** (tie-break by smallest `tc_id`).

3) If all TCs are compliant, select the TC with the **smallest compliance margin** to the nearest limit (tie-break by smallest `tc_id`).

How to compute “violation magnitude” and “margin” for common spec shapes:
- Upper-only limit `value <= U`:
  - violation = `max(value - U, 0)`
  - margin (if compliant) = `U - value`
- Lower-only limit `value >= L`:
  - violation = `max(L - value, 0)`
  - margin (if compliant) = `value - L`
- Two-sided window `L <= value <= U` (e.g., TAL):
  - violation = `max(L - value, value - U, 0)`
  - margin (if compliant) = `min(value - L, U - value)`

Null/uncomputable metric handling in this fallback:
- Treat `value is None` as non-compliant for selection purposes (cannot demonstrate compliance).
- If multiple TCs are None, select smallest `tc_id` deterministically.

This fallback does NOT introduce extra assumptions like “tie-break by minimum peak” unless the handbook explicitly states such a tie-break.


## E) Deterministic tie-break patterns (FIXED, implementable)

Rule: always break ties by smallest `tc_id` (lexicographic) unless the handbook says otherwise.

Given `items = [{"tc_id":..., "value":...}, ...]`:

```python
# choose maximum value, tie -> smallest tc_id
best = sorted(items, key=lambda x: (-x["value"], x["tc_id"]))[0]

# choose minimum value, tie -> smallest tc_id
best = sorted(items, key=lambda x: (x["value"], x["tc_id"]))[0]
```

(Do not use undefined helpers like lex(), and do not rely on negating strings.)


## F) Peak computation (common pattern; still handbook-driven)
Per TC:
- `peak_tc = max(temp_c)`
If the handbook states “all monitored points must reach minimum peak”, run-level worst-case is:
- `min_peak_run = min(peak_tc)` (tie by smallest tc_id)

Requirement may be a fixed minimum peak OR derived (e.g., liquidus + margin). Only use what the handbook specifies.


## G) Conveyor feasibility (handbook-specific)
Handbooks vary. Represent the rule as a structured object and compute feasibility only if the handbook provides a computable relationship.

Common patterns (ONLY if handbook states them):
- Given effective heated length `L_eff_cm` and max allowed time-in-oven `t_max_s`:
  - `speed_min_cm_min = (L_eff_cm / t_max_s) * 60`
- Given `L_eff_cm` and minimum required dwell `t_min_s`:
  - `speed_max_cm_min = (L_eff_cm / t_min_s) * 60` (note: that is a maximum speed constraint, not a minimum)

If required parameters are missing/unmappable, output null for required fields and set `meets = false` (cannot demonstrate feasibility).


## H) Output construction guardrails

### H1. Sorting
- Lists: sort by primary ID (run_id / board_family) lexicographically.
- Dicts keyed by ID: emit in sorted key order.

### H2. Rounding and NaNs
- Round floats to 2 decimals.
- Never emit NaN/Inf; use null.

```python
import math

def r2(x):
    if x is None:
        return None
    try:
        xf = float(x)
    except Exception:
        return None
    if math.isnan(xf) or math.isinf(xf):
        return None
    return float(round(xf, 2))
```

### H3. Missing thermocouple data
If a run has no TC records (or no valid segments for a metric), set metric outputs to null. Do not claim “pass” unless the handbook and task explicitly allow it.


## I) Minimal end-to-end scaffold

```python
import os, json
import pandas as pd

DATA_DIR = "/app/data"
OUT_DIR  = "/app/output"

runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))

runs["run_id"] = runs["run_id"].astype(str)
tc["run_id"]   = tc["run_id"].astype(str)
tc["tc_id"]    = tc["tc_id"].astype(str)

runs = runs.sort_values(["run_id"], kind="mergesort")
tc   = tc.sort_values(["run_id", "tc_id", "time_s"], kind="mergesort")

# 1) Retrieve cfg from handbook (via text extraction + regex + context checks)
cfg = {...}

# 2) Compute per-run metrics deterministically with stable tie-breaks and interpolation
# 3) Build JSON outputs with sorted IDs and 2dp rounding
# 4) Write requested artifacts into /app/output
```
