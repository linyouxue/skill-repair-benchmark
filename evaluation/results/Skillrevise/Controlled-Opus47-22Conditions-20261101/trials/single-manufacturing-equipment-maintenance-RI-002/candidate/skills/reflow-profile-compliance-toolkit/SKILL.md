---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval and thermocouple computations for reflow profile compliance outputs such as ramp, TAL, peak, feasibility, and selection.
---

# Reflow Profile Compliance Toolkit

## Mandatory execution and completion contract

For a concrete reflow-compliance task, the requested deliverable files are the completion condition. Do not finish after describing the next action, inspecting inputs, checking tool availability, or computing only an intermediate value. Continue making real tool calls until every requested output exists and has been parsed back successfully.

For the manufacturing-equipment-maintenance task that requests `/app/output/q01.json` through `/app/output/q05.json`, all five files are mandatory. Treat this as a blocking invariant:

1. Create `/app/output` before analysis.
2. Inspect the CSV schemas and extract the needed handbook rules. If a read-only command fails, immediately retry with a simpler valid command; an announced retry is not work completed.
3. Prefer building one deterministic Python program, for example `/app/solve_reflow.py`, that loads all source data once, computes all five answers, and writes all five JSON files. This reduces fragile multi-command handoffs.
4. Do not stop merely to probe optional PDF libraries. First try an already-available local extractor such as `pdftotext`; if it is unavailable, use an installed Python PDF reader or another local method. Tool discovery is only a prerequisite and never a terminal state.
5. After writing the outputs, run a real completion check that opens and `json.load`s each of `q01.json`, `q02.json`, `q03.json`, `q04.json`, and `q05.json`.
6. Verify coverage against the visible task inputs before finishing:
   - Q01 has a record for every `run_id` in `mes_log.csv`.
   - Q02 contains at least one record for every `run_id`, is sorted by `run_id`, and each record's `tc_id` is the handbook representative sensor (see "Representative thermocouple selection" below).
   - Q03 contains a `failing_runs` list and run-level peak information.
   - Q04 contains one record for every `run_id`, with the actual conveyor speed and a boolean feasibility field, sorted by `run_id`.
   - Q05 contains exactly one record per `board_family`; `best_run_id` and every runner-up must belong to that family, and runner-up IDs are sorted.
7. Never intentionally finish while any required output is missing, empty, invalid JSON, or known to have incomplete ID coverage. If a tool call fails, repair the command and continue within the remaining iteration budget.

A suitable final check is:

```python
from pathlib import Path
import json

out = Path("/app/output")
required = [out / f"q0{i}.json" for i in range(1, 6)]
for path in required:
    assert path.is_file() and path.stat().st_size > 0, path
    with path.open("r", encoding="utf-8") as f:
        json.load(f)
print("all five required JSON outputs exist and parse")
```

Only after this check and the task-specific coverage checks pass may the task be considered complete.

## When to invoke

1. Whenever the task involves reflow related questions from thermocouple data, MES data or defect data and handbook-defined regions/windows/limits.
2. Extract numeric limits / temperature regions / timing windows / margins / feasibility rules from handbook.pdf.
3. Compute run-level metrics from time-temperature thermocouple traces in a deterministic way.

This skill is designed to make the agent:
- retrieve the right definitions from the handbook,
- bind sensor selection to handbook-defined physical location semantics, and
- compute metrics with predictable tie-breaks and interpolation.

## Handbook "where to look" checklist

Search the handbook for these common sections/tables:
- Thermal profile overview: defines "preheat", "soak", "reflow", "cooling".
- Ramp rate guidance: "ramp", "slope", "C/s".
- Liquidus and wetting time: "liquidus", "time above liquidus", "TAL", "wetting".
- Peak temperature guidance: "peak", "minimum peak", "margin above liquidus".
- Conveyor / dwell feasibility: "conveyor speed", "dwell time", "heated length", "zone length", "time-in-oven".
- Thermocouple placement and representativeness: "cold spot", "hot spot", "worst case", "largest mass", "representative sensor", "coldest point", "critical component".

Goal: extract a compact config object from the handbook and use it for all computations:

```python
cfg = {
  "preheat_region": {...},   # temp_band | zone_band | time_band
  "ramp_limit_c_per_s": ...,

  "tal_threshold_c_source": "solder_liquidus_c",
  "tal_min_s": ...,
  "tal_max_s": ...,

  "peak_margin_c": ...,

  "conveyor_rule": {...},

  # Representative-sensor policy per metric. Each entry is an ORDERED list of
  # location tokens (lowercased, substrings allowed) that the handbook maps to
  # the "representative" / "worst-case" TC for that metric. The FIRST match wins.
  "representative_tc_policy": {
     "ramp":  [...],   # e.g. ["largest_mass", "cold_spot"] if handbook says so
     "tal":   [...],   # typically coldest / largest-mass point for TAL
     "peak":  [...],   # typically coldest / largest-mass point for min peak
  },
}
```

If the handbook provides multiple applicable constraints, implement all and use the stricter one.

## Representative thermocouple selection (handbook-grounded)

The representative TC per run is defined by the handbook's physical-location semantics, not by the metric value. Do not short-circuit this to "min TAL + smallest tc_id".

Required procedure for each metric M in {ramp, tal, peak}:

1. Read `cfg["representative_tc_policy"][M]`, an ordered list of location tokens taken verbatim from the handbook (e.g., `largest_mass`, `cold_spot`, `worst_case`, `coldest_point`).
2. Discover the location column in `thermocouples.csv` (or an adjacent mapping file). Typical names: `tc_location`, `location`, `tc_role`, `placement`. If no location column is present, see fallback below.
3. For each run, iterate the policy tokens in order. For each token, select the TCs whose location string (lowercased) contains the token.
   - If exactly one TC matches, use it.
   - If multiple TCs match, break ties with the metric-appropriate numeric rule and then by smallest `tc_id`:
     - "max" metric (ramp): choose highest value, then smallest `tc_id`.
     - "min" metric (coldest TAL, coldest peak): choose lowest value, then smallest `tc_id`.
4. If no token in the policy matches any TC for that run, fall back as follows and log the fallback:
   - "max" metric: choose `(max_value, smallest_tc_id)`.
   - "min" metric: choose `(min_value, smallest_tc_id)`.
5. Log one audit line per run: `run_id, metric, chosen_tc_id, chosen_location, source in {location_match, fallback_numeric}`. These logs must be printed before writing the JSON outputs so the choice is auditable.

Reference implementation:

```python
def pick_representative_tc(per_tc_rows, policy_tokens, direction, location_col):
    """
    per_tc_rows: list of dicts with keys tc_id, value, and optionally location_col
    policy_tokens: ordered list of lowercased substrings from handbook
    direction: "max" or "min"
    location_col: name of the location column, or None
    Returns (chosen_row, source)
    """
    def numeric_pick(rows):
        if direction == "max":
            return max(rows, key=lambda r: (r["value"], -_lex(r["tc_id"])))
        return min(rows, key=lambda r: (r["value"], r["tc_id"]))

    if location_col:
        for tok in policy_tokens:
            matches = [r for r in per_tc_rows
                       if tok in str(r.get(location_col, "")).lower()]
            if matches:
                return numeric_pick(matches), "location_match"
    return numeric_pick(per_tc_rows), "fallback_numeric"
```

Only after this selector returns the representative TC do you emit its `tc_id` and metric value to the output JSON.

## Deterministic thermocouple computation recipes

### 1. Sorting and de-dup rules

Always sort samples by time before any computation:

```python
df_tc = df_tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")
```

Ignore segments where `dt <= 0`.

### 2. Segment slope (ramp rate)

Finite-difference slope on consecutive samples. Max ramp is `max(s_i)` over the region.

Region filtering patterns:
- Temperature band: both segment endpoints satisfy `tmin <= T <= tmax`.
- Zone band: filter by `zone_id in zones`.
- Time band: filter by `t_start_s <= time_s <= t_end_s`.

```python
def max_slope_in_temp_band(df_tc, tmin, tmax):
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    best = None
    for i in range(1, len(g)):
        dt = t[i] - t[i-1]
        if dt <= 0: continue
        if (tmin <= y[i-1] <= tmax) and (tmin <= y[i] <= tmax):
            s = (y[i] - y[i-1]) / dt
            best = s if best is None else max(best, s)
    return best
```

### 3. Time above threshold with linear interpolation

```python
def time_above_threshold_s(df_tc, thr):
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    total = 0.0
    for i in range(1, len(g)):
        t0, t1 = t[i-1], t[i]
        y0, y1 = y[i-1], y[i]
        if t1 <= t0: continue
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

### 4. Metric computation flow

For each run and each metric M:

1. Compute the per-TC metric value for every TC in the run.
2. Call `pick_representative_tc(...)` with the handbook policy for M.
3. Emit `(chosen_tc_id, metric_value)` to the output.

Do not pick the TC first based on a value-only rule and then compute; always compute per-TC then select by location policy.

### 5. Peak and margin

Per TC: `peak_tc = max(temp_c)`.
Run-level representative peak: use the representative-TC policy for peak (handbook-defined coldest/largest-mass point).
Requirement: `required_peak = liquidus + peak_margin` (per handbook).

### 6. Conveyor feasibility

Represent the rule as a structured object. Common patterns:

- Minimum dwell `t_min_s` across effective heated length `L_eff_cm`:
  `speed_max_cm_min = (L_eff_cm / t_min_s) * 60` -> interpret per handbook which direction is "min feasible speed".
- Maximum time-in-oven `t_max_s` across `L_eff_cm`:
  `speed_min_cm_min = (L_eff_cm / t_max_s) * 60`.

If parameters are missing: `required_min_speed_cm_min = null`, `meets = false`.

## Output construction guardrails

### 1. Sorting
- Lists: sort by primary ID (run_id / board_family / board_id) lexicographically ascending.
- Dicts keyed by ID: emit in sorted key order.

### 2. Rounding and NaNs
- Round floats to 2 decimals.
- Never emit NaN/Inf; use `null`.

```python
def r2(x):
    if x is None: return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)): return None
    return float(round(float(x), 2))
```

### 3. Missing thermocouple data
If a run has no TC records (or no valid segments for a metric), set numeric outputs to `null`. For Q03, a run with no thermocouple data is failing per task statement.

## Post-write schema and representative-sensor checks

Before claiming completion, reload each output and assert its schema. Example for Q02:

```python
import json
rec = json.load(open("/app/output/q02.json"))
assert isinstance(rec, list) and rec, "q02 empty"
seen = set()
for r in rec:
    for k in ("run_id","tc_id","tal_s","required_min_tal_s","required_max_tal_s","status"):
        assert k in r, (k, r)
    assert r["status"] in ("compliant","non-compliant"), r
    seen.add(r["run_id"])
# every run in mes_log.csv must appear
# every tc_id must equal the audit-logged representative TC for that run
```

Also assert, for every run, that `q02[*].tc_id` equals the `chosen_tc_id` printed by the representative-TC audit log for metric `tal`. If any mismatch, do not finalize; recompute.

## Minimal end-to-end scaffold

```python
import os, json, math
import pandas as pd

DATA_DIR = "/app/data"
OUT_DIR  = "/app/output"
os.makedirs(OUT_DIR, exist_ok=True)

runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))

for df, cols in [(runs, ["run_id"]), (tc, ["run_id","tc_id"])]:
    for c in cols: df[c] = df[c].astype(str)

tc = tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")

# 1) Parse handbook into cfg, INCLUDING representative_tc_policy per metric.
cfg = {...}

# 2) Discover the location column name in tc (e.g., tc_location) or None.
LOCATION_COL = next((c for c in ["tc_location","location","placement","tc_role"]
                     if c in tc.columns), None)

# 3) For each run+metric: compute per-TC values, then pick representative TC
#    via pick_representative_tc using cfg["representative_tc_policy"][metric].
#    Print one audit line per (run_id, metric).

# 4) Build JSON objects with sorted IDs and 2dp rounding.

# 5) Write q01..q05, then reload and run schema + representative-TC consistency
#    assertions before finishing.
```

Sanity checks before writing outputs:
- ID fields are strings.
- Arrays sorted lexicographically ascending by the specified key.
- Floats rounded to 2 decimals.
- No NaN/Inf in JSON.
- Representative-TC selection used the handbook location policy; fallback to numeric tie-break only when no location token matched, and that fallback is logged.
- Any "time above threshold" uses interpolation.
- Every requested output file exists, is nonempty, parses as JSON, and has complete visible-ID coverage before completion.