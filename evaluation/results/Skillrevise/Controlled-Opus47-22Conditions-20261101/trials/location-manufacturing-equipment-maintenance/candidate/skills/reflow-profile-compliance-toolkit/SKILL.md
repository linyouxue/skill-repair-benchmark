---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval and thermocouple computations for reflow profile compliance outputs such as ramp, TAL, peak, feasibility, and selection.
---

When to invoke:
1. Whenever the task involves reflow related questions from thermocouple data, MES data or defect data and handbook-defined regions/windows/limits.
2. Extract numeric limits, temperature regions, timing windows, margins, and feasibility rules from handbook.pdf.
3. Compute run-level metrics from time-temperature thermocouple traces in a deterministic way.

This skill is designed to make the agent:
- retrieve the right definitions from the handbook, including which thermocouple location is representative, and
- compute metrics with predictable tie-breaks and interpolation.

Inputs (discover, do not hardcode beyond these paths)
- /app/data/handbook.pdf
- /app/data/mes_log.csv
- /app/data/thermocouples.csv
- /app/data/test_defects.csv

Before computing anything, inspect each CSV's actual columns (do not assume names). The thermocouple table is expected to carry at least a run_id, tc_id, time_s, temp_c, and a location descriptor (for example tc_location with values such as largest_mass, smallest_mass, center_BGA, edge, corner). MES is expected to carry per-run metadata such as board_family, board_id, solder_liquidus_c, conveyor speed, and possibly zone or geometry fields. If a column name differs, map it locally; never invent values.

Handbook "where to look" checklist

Search the handbook for these sections and record what you find into a cfg object:
- Thermal profile overview: definitions of preheat, soak, reflow, cooling.
- Ramp rate guidance: ramp, slope, deg C/s, applicable region (temperature band, zone band, or time band).
- Liquidus and wetting time: liquidus temperature, time above liquidus (TAL), min and max TAL window.
- Peak temperature guidance: minimum peak, margin above liquidus, worst-case sensor rule.
- Conveyor and dwell feasibility: conveyor speed, dwell time, heated length, zone length, time-in-oven.
- Thermocouple placement and representative sensor: which physical location is defined as the worst-case or representative sensor for TAL and peak compliance (for example largest thermal mass as the slowest-heating worst case).

Extract a compact cfg object and reuse it for all computations:

```python
cfg = {
  # ramp region: one of
  #   {"type":"temp_band", "tmin":..., "tmax":...}
  #   {"type":"zone_band", "zones":[...]}
  #   {"type":"time_band", "t_start_s":..., "t_end_s":...}
  "preheat_region": {...},
  "ramp_limit_c_per_s": ...,

  "tal_threshold_c_source": "solder_liquidus_c",   # per-run from MES
  "tal_min_s": ...,
  "tal_max_s": ...,

  "peak_margin_c": ...,

  # Representative sensor rule read from the handbook.
  # Expressed as an ordered preference list over tc_location values.
  # Example (handbook-dependent): ["largest_mass", "center_BGA"].
  "representative_tc_location_order_tal":  [...],
  "representative_tc_location_order_peak": [...],
  # When ramp uses a different placement (often any TC inside region), record it too.
  "representative_tc_location_order_ramp": [...],  # may be [] meaning: use all TCs

  "conveyor_rule": {...},   # structured; see below
}
```

If the handbook provides multiple applicable constraints, implement all and apply the stricter one; document the choice in code comments.

Deterministic thermocouple computation recipes

1. Sorting and dedup
```python
df_tc = df_tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")
```
Ignore segments where dt <= 0 (non-monotonic timestamps).

2. Segment slope (ramp rate)
Finite-difference slope on consecutive samples:
- s_i = (T_i - T_{i-1}) / (t_i - t_{i-1}) for dt > 0
- max ramp over region = max(s_i)

Region filters:
- temp_band: include a segment only when both endpoints lie in [tmin, tmax].
- zone_band: filter rows by zone_id in zones.
- time_band: filter rows by t_start_s <= time_s <= t_end_s.

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

3. Time above threshold (TAL) with linear interpolation
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
        if y0 > thr and y1 > thr:
            total += (t1 - t0); continue
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

4. Representative sensor selection (handbook-grounded, not value-based)

Rule: the "representative" or "worst-case" thermocouple for TAL and peak compliance is defined by the handbook in terms of physical placement (for example largest thermal mass is the slowest-heating worst case). Do not pick by raw metric value as the primary criterion.

Procedure for each run:
1. Compute the per-TC metric for every TC in that run (TAL seconds, or peak temperature).
2. Build the preference list from cfg (for example representative_tc_location_order_tal). The handbook decides this list; do not invent entries.
3. Among the run's TCs, keep only those whose tc_location equals the first preference. If none, fall back to the next preference, and so on.
4. If multiple TCs remain after location filtering, apply a documented, stable tie-break: for TAL/peak worst case prefer the smaller value (slowest heating), then the lexicographically smallest tc_id.
5. If a run has no tc_location column at all, record this in a comment and fall back to the stable tie-break (min value then min tc_id), but mark the row for review.
6. For ramp, apply the handbook rule; if it does not specify a placement, use all TCs in the ramp region and pick the maximum slope across TCs with lexicographic tc_id tie-break.

Pseudocode:
```python
def pick_representative(tc_metrics, loc_order, mode):
    # tc_metrics: list of (tc_id, tc_location, value) for one run
    # mode: "worst_case_min" (TAL/peak) or "worst_case_max" (ramp)
    for loc in loc_order or []:
        cand = [m for m in tc_metrics if m.tc_location == loc and m.value is not None]
        if cand:
            if mode == "worst_case_min":
                cand.sort(key=lambda m: (m.value, m.tc_id))
            else:
                cand.sort(key=lambda m: (-m.value, m.tc_id))
            return cand[0]
    # fallback: no preferred location found
    cand = [m for m in tc_metrics if m.value is not None]
    if not cand:
        return None
    if mode == "worst_case_min":
        cand.sort(key=lambda m: (m.value, m.tc_id))
    else:
        cand.sort(key=lambda m: (-m.value, m.tc_id))
    return cand[0]
```

5. Peak and margin
Per TC: peak_tc = max(temp_c).
Run-level representative peak = pick_representative with the peak preference list and worst_case_min semantics (coldest among representative placements).
Required minimum peak = solder_liquidus_c + peak_margin_c (from cfg).
A run with no thermocouple data is failing (per task statement in Q3).

6. Conveyor feasibility
Represent the handbook rule as a structured object. Common patterns:
- Minimum dwell across effective heated length L_eff_cm with minimum dwell t_min_s:
  speed_min_cm_min = (L_eff_cm / t_min_s) * 60 and actual speed must be <= that value, i.e. required_min_speed is actually a maximum feasible speed; follow the handbook wording.
- Maximum time-in-oven t_max_s over L_eff_cm:
  speed_min_cm_min = (L_eff_cm / t_max_s) * 60.
If parameters are missing: required_min_speed_cm_min = null and meets = false.

Output construction guardrails

1. Sorting
- Lists: sort by primary ID (run_id, board_family, or board_id) lexicographically ascending.
- Dicts keyed by ID: emit keys in sorted order.

2. Rounding and NaNs
```python
def r2(x):
    if x is None: return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)): return None
    return float(round(float(x), 2))
```
Never emit NaN or Inf; use null.

3. Missing data
If a run has no TC rows (or no valid segments for a metric), set numeric outputs to null. Do not claim pass unless the task statement allows it. Q3 explicitly treats such runs as failing.

Deliverables (must all be produced before finishing)

Produce exactly these five files:
- /app/output/q01.json
  Shape:
  {
    "ramp_rate_limit_c_per_s": <float>,
    "violating_runs": ["R...."],
    "max_ramp_by_run": { "R....": {"tc_id": "<str or null>", "max_preheat_ramp_c_per_s": <float or null>}, ... }
  }
- /app/output/q02.json
  Shape: list of {run_id, tc_id, tal_s, required_min_tal_s, required_max_tal_s, status in {"compliant","non-compliant"}}
  tc_id must come from the TAL representative-sensor rule (location-filtered first).
- /app/output/q03.json
  Shape:
  {
    "failing_runs": ["R...."],
    "min_peak_by_run": { "R....": {"tc_id": "<str or null>", "peak_temp_c": <float or null>, "required_min_peak_c": <float or null>}, ... }
  }
  Runs with no thermocouple data appear in failing_runs with null numeric fields.
- /app/output/q04.json
  Shape: list of {run_id, required_min_speed_cm_min, actual_speed_cm_min, meets (bool)}
- /app/output/q05.json
  Shape: list of {board_family, best_run_id, runner_up_run_ids: ["R...."]}
  Base best-run selection on quality (compliance across Q01-Q04 and defect counts) and efficiency (throughput or dwell margin) using only handbook- or MES-grounded signals; document the ranking rule in code comments.

Minimal end-to-end scaffold

```python
import os, json, math
import pandas as pd

DATA_DIR = "/app/data"
OUT_DIR  = "/app/output"
os.makedirs(OUT_DIR, exist_ok=True)

runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))
defs = pd.read_csv(os.path.join(DATA_DIR, "test_defects.csv"))

for df, cols in [(runs, ["run_id"]), (tc, ["run_id","tc_id"])]:
    for c in cols:
        df[c] = df[c].astype(str)

runs = runs.sort_values(["run_id"], kind="mergesort")
tc   = tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")

# 1) Retrieve cfg from handbook via PDF reading / RAG:
#    - preheat_region, ramp_limit
#    - tal_min_s, tal_max_s (liquidus comes per-run from MES)
#    - peak_margin_c
#    - representative_tc_location_order_tal / _peak / _ramp
#    - conveyor_rule
cfg = {...}

# 2) Compute per-run metrics with the recipes above and pick_representative(...)
# 3) Build JSON objects with sorted IDs, r2 rounding, null handling
# 4) Write q01..q05 to /app/output
# 5) Run the pre-finish verification pass below
```

Pre-finish verification pass (mandatory execution anchor)

After writing the files and before claiming completion, reload each output and assert the following. If any assertion fails, fix the generator and rewrite the file; do not finalize until all pass.

```python
import json, os

REQUIRED = ["q01.json","q02.json","q03.json","q04.json","q05.json"]
for name in REQUIRED:
    path = os.path.join(OUT_DIR, name)
    assert os.path.exists(path), f"missing {path}"
    with open(path) as f:
        data = json.load(f)   # must parse

# Shape checks (adapt to each schema listed in Deliverables)
# - q01: top-level dict with the three keys; violating_runs is a sorted list of strings;
#        max_ramp_by_run keys are sorted ascending.
# - q02: list sorted by run_id ascending; each item has all six keys; status in the allowed set.
# - q03: top-level dict; failing_runs sorted; min_peak_by_run keys sorted;
#        every run with no TC data appears in failing_runs with null numeric fields.
# - q04: list sorted by run_id ascending; meets is a bool.
# - q05: list sorted by board_family ascending; runner_up_run_ids is a sorted list.

# Numeric hygiene: no NaN/Inf; floats are rounded to 2 decimals.
# Sensor-selection semantics: for q02 and q03, confirm each recorded tc_id
# was selected via the handbook location preference list (not by raw metric value alone).
# For runs where location filtering fell back, log the fallback for review.
```

Sanity checks summary
- ID fields are strings.
- Arrays sorted lexicographically by the specified key.
- Floats rounded to 2 decimals; no NaN/Inf; null where missing.
- TAL and peak representative TC selected by tc_location preference from the handbook; value-based tie-break only within the filtered set or as documented fallback.
- Ramp selection follows the handbook; if unspecified, use the max slope across all in-region TCs with lexicographic tc_id tie-break.
- Q3 runs with no TC data are listed as failing.
- All five output files exist, parse as JSON, and match their schemas.