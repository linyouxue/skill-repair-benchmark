---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval and thermocouple computations for reflow profile compliance outputs such as ramp, TAL, peak, feasibility, and selection.
---



When to invoke:
1. Whenever the task involves reflow related questions from thermocouple data, MES data or defect data and handbook-defined regions/windows/limits.
2. Extract numeric limits / temperature regions / timing windows / margins / feasibility rules from handbook.pdf.
3. Compute run-level metrics from time–temperature thermocouple traces in a deterministic way.

This skill is designed to make the agent:
- retrieve the right definitions from the handbook, and  
- compute metrics with predictable tie-breaks and interpolation.



Handbook “where to look” checklist

Search the handbook for these common sections/tables:
- Thermal profile overview: defines “preheat”, “soak”, “reflow”, “cooling”.
- Ramp rate guidance: “ramp”, “slope”, “°C/s”, “C/s”.
- Liquidus & wetting time: “liquidus”, “time above liquidus”, “TAL”, “wetting”.
- Peak temperature guidance: “peak”, “minimum peak”, “margin above liquidus”.
- Conveyor / dwell feasibility: “conveyor speed”, “dwell time”, “heated length”, “zone length”, “time-in-oven”.
- Thermocouple placement: “cold spot”, “worst case”, “representative sensor”.

Goal: extract a compact config object from the handbook and use it for all computations:

```python
cfg = {
  # temperature region for the ramp calculation:
  # either {"type":"temp_band", "tmin":..., "tmax":...}
  # or {"type":"zone_band", "zones":[...]}
  # or {"type":"time_band", "t_start_s":..., "t_end_s":...}
  "preheat_region": {...},

  "ramp_limit_c_per_s": ...,

  "tal_threshold_c_source": "solder_liquidus_c",   # if MES provides it
  "tal_min_s": ...,
  "tal_max_s": ...,

  "peak_margin_c": ...,

  # conveyor feasibility can be many forms; represent as a rule object
  "conveyor_rule": {...},
}
```

If the handbook provides multiple applicable constraints, retain every constraint in `cfg` and evaluate their intersection. Do not collapse them into a generic rule or choose a value by plausibility. Preserve each constraint's units, inequality direction, applicability condition, and inclusive/exclusive boundary. A missing, ambiguous, contradictory, or unit-incompatible required handbook field makes the affected result unavailable rather than permitting an inferred value.



Deterministic thermocouple computation recipes

1. Input validation and ordering
Convert `run_id` and `tc_id` to strings. Reject or exclude rows with non-finite `time_s` or `temp_c`; do not coerce them to zero. Sort with a stable sort by `run_id`, `tc_id`, and `time_s`. Within each run/TC series, a segment is usable only when both endpoint values are finite and `dt = t1 - t0 > 0`; never bridge duplicate, reversed, or invalid timestamps.

2. Handbook region semantics and ramp
Use the exact preheat region in `cfg`; do not substitute a remembered temperature band. For a temperature-band region, include a segment only when both endpoint temperatures satisfy every configured bound, with inclusivity exactly as specified by the handbook. For a time-band or zone-band region, apply its configured endpoint or zone predicate to the segment. Compute each valid finite-difference slope as `(T1-T0)/(t1-t0)`. The ramp metric is the maximum positive slope; zero and negative slopes are not positive-ramp violations. If no valid positive slope exists, the metric is null (not zero). Compare to the handbook limit using its stated boundary convention.

3. TAL with piecewise-linear crossings
Resolve the liquidus threshold from the configured handbook source and the applicable MES value. Integrate each valid segment's duration strictly above the threshold, unless the handbook explicitly defines an inclusive boundary. For a crossing, use linear interpolation `t_cross = t0 + (thr-T0)/(T1-T0)*(t1-t0)` and add only the above-threshold portion. A segment whose endpoints are both strictly above contributes its full duration; segments at or below the strict threshold contribute no duration. Do not count invalid or non-increasing segments, and do not round during integration. Missing threshold, unusable trace, or no valid segment yields null TAL and a non-compliant Q02 status.

4. Peak and metric-specific sensor reduction
Compute a per-TC peak as the maximum finite temperature in that TC's valid samples. Apply the handbook's sensor-placement rule first (for example representative, cold-spot, or required sensor). If the handbook requires a worst-case reduction, evaluate all applicable sensors and use the limiting direction for that metric: maximum ramp, minimum TAL when a minimum is required, maximum TAL when a maximum is required, and minimum peak when a minimum peak is required. Do not use one universal reduction direction for all metrics. For equal numeric values, choose the lexicographically smallest string `tc_id`. If no applicable sensor or valid value exists, return null; never fabricate a sensor or zero. Q03 marks a run failing when required TC data is absent or its required peak is unavailable.

5. Conveyor feasibility as constraint intersection
Construct all applicable handbook speed constraints after applying the handbook's board geometry and unit conversions. Derive each lower bound and upper bound explicitly: for a maximum dwell, speed must be at least `60*L_eff_cm/t_max_s`; for a minimum dwell, speed must be at most `60*L_eff_cm/t_min_s`; also apply explicit machine speed limits and any board-specific bounds. `required_min_speed_cm_min` is the maximum applicable lower bound only when that bound is derivable; retain upper bounds separately for the `meets` test. Feasibility is true only if actual speed is finite and satisfies every bound with the handbook's exact inclusivity, and all required geometry, dwell, and speed inputs are valid. Missing or contradictory inputs yield a null derived requirement and `meets: false`.

6. Missing-data rule
A missing run, missing required thermocouple, missing handbook value, invalid unit, or unusable metric must produce JSON null for affected numeric fields and the prescribed failing/non-compliant/false result. Never infer missing values from neighboring runs, treat missing defects as zero, or claim compliance from absence of evidence.



Output construction and Q01-Q05 contract

Write exactly `/app/output/q01.json` through `/app/output/q05.json`, creating the directory if necessary. Validate each object against the task schema before writing. Q01 contains the handbook ramp limit, sorted violating run IDs, and sorted run entries with the selected `tc_id` and ramp (null when unavailable). Q02 contains one sorted record per run with selected `tc_id`, TAL, handbook min/max TAL, and exactly `compliant` or `non-compliant`; null TAL is non-compliant. Q03 contains sorted failing run IDs and selected `tc_id`, peak, and required peak fields; missing TC data is failing with null metrics. Q04 contains sorted run records with the derived lower-bound speed, actual MES speed, and boolean `meets`; missing or invalid required data is false. Q05 contains one sorted record per `board_family`, with the best run and all other candidate IDs.

Sort all arrays and keyed objects lexicographically by their required ID fields, keep IDs as strings, and preserve full precision until final serialization. Round finite numeric values to two decimals only at serialization. Convert every NaN or infinity to JSON null; never emit nonstandard JSON values.

For Q05, group only by `board_family` and use only handbook/task-defined defect, compliance, quality, and efficiency fields. Rank quality first: prefer candidates satisfying all applicable compliance checks, then apply the handbook-defined defect/quality direction and missing-data policy. Rank efficiency second using the handbook-defined metric and direction. Do not treat missing quality, defects, compliance, or efficiency as zero or as an implied pass. Use lexicographically ascending `run_id` as the final tie-break. Emit the first ranked ID as `best_run_id` and the remaining ranked IDs in that same deterministic order as `runner_up_run_ids`. If a required ranking input is unavailable, follow the handbook's explicit policy; otherwise retain deterministic ID order without inventing a value.

Before completion, parse every output as JSON and verify required keys, value types, null/boolean/status conventions, ordering, two-decimal serialization, and file existence.


## Minimal end-to-end scaffold

```python
import os, json, math
import pandas as pd

DATA_DIR = "/app/data"
OUT_DIR  = "/app/output"

runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))

runs["run_id"] = runs["run_id"].astype(str)
tc["run_id"]   = tc["run_id"].astype(str)
tc["tc_id"]    = tc["tc_id"].astype(str)

runs = runs.sort_values(["run_id"], kind="mergesort")
tc   = tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")

# 1) Read handbook.pdf first and build one validated cfg containing only sourced
#    regions, thresholds, windows, sensor rules, geometry, speed bounds, units,
#    inequality directions, and boundary conventions.
# 2) Validate required CSV columns and finite typed values; normalize string IDs.
# 3) Compute Q01-Q04 from the same cfg using the recipes above, retaining full
#    precision and applying metric-specific sensor reduction and deterministic ties.
# 4) Compute Q05 only from available handbook/task-defined quality and efficiency
#    fields; never fabricate missing values.
# 5) Validate each required JSON schema, ordering, null/boolean/status values, and
#    NaN protection, then serialize rounded values to /app/output/q01.json ... q05.json.
```

---

Sanity checks before writing outputs
- ID fields are strings.
- Arrays sorted lexicographically.
- Floats rounded to 2 decimals.
- No NaN/Inf in JSON.
- Sensor selection uses deterministic tie-breaks.
- Any “time above threshold” uses interpolation (not naive threshold counting).
