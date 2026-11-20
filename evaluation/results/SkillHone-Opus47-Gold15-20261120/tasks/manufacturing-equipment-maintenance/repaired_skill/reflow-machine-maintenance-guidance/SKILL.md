---
name: reflow-machine-maintenance-guidance
description: This skill should be considered when you need to answer reflow machine maintenance questions or provide detailed guidance based on thermocouple data, MES data or defect data and reflow technical handbooks. This skill covers how to obtain important concepts, calculations, definitions, thresholds, and others from the handbook and how to do cross validations between handbook and datasets.
---

This skill should be considered when you need to answer reflow equipment maintenance questions based on thermocouple data, MES data, defect data, and reflow technical handbooks. Based on the questions, first retrieve related info from the handbook and corresponding datasets. Most frequently asked concepts include preheat, soak, reflow, cooling, ramp, slope, C/s, liquidus and wetting time, ramp rate guidance, time above liquidus, TAL, peak temperature guidance, minimum peak, margin above liquidus, conveyor speed, dwell time, heated length, zone length, time-in-oven, thermocouple placement, cold spot, worst case, representative sensor, numeric limits, temperature regions, etc. If the handbook provides multiple values or constraints, implement all and use the stricter constraint or the proper value.

Common equations used in manufacturing reflow machines include the max ramp is max(s_i) over the region, where s_i = (T_i - T_{i-1}) / (t_i - t_{i-1}) for dt > 0. For the temperature band region, only consider segments where both endpoints satisfy tmin <= T <= tmax. For the zone band region, only consider zone_id in zones. For time band region, only consider t_start_s <= time_s <= t_end_s. For wetting/TAL-type metrics, compute time above a threshold `thr` using segment interpolation. For each TC, peak_tc = max(temp_c). min_peak_run = min(peak_tc), and required_peak = liquidus + peak_margin.

Per-run thermocouple reduction. Every TC-driven run-level question requires the same deterministic pipeline: (1) group thermocouple rows by (run_id, tc_id); (2) compute the per-TC metric (ramp in the preheat band, time above liquidus, peak, etc.) for *every* TC in the run; (3) reduce across TCs by the direction of the question — take the maximum for "max ramp" / "highest peak" / "overshoot" questions and the minimum for "min peak" / "coldest" / "worst-case TAL" questions, with tie-break (value, tc_id ASC); (4) report the `tc_id` that produced the reduced value. Do **not** pre-filter the thermocouple dataframe to a single `tc_location` before computing the metric — compute first, reduce second.

Representative-sensor language in the handbook ("cold spot", "worst case", "coldest sensor", "hottest sensor") describes which placement is *expected* to dominate the metric; it does not override the data. If `tc_location` exists, use it to sanity-check that the TC selected by the per-TC reduction lands on a plausible placement (e.g., a min-peak question usually lands on the highest-thermal-mass placement), but when the data disagrees with the expectation, keep the data-driven selection and inspect the data rather than forcing the "expected" placement.

For conveyor feasibility, a time/dwell window implies a speed window. Speed and dwell are inversely related, so be careful which side you are computing. Given effective heated length L_eff_cm, a minimum dwell t_min_s maps to the maximum allowable speed: speed_max_cm_min = (L_eff_cm / t_min_s) * 60. A maximum dwell / time-in-oven t_max_s maps to the minimum allowable speed: speed_min_cm_min = (L_eff_cm / t_max_s) * 60. Only use L_eff_cm values that come from the handbook (e.g., the heated/process area or reflow-zone length stated for the oven model); do not substitute the board length for the oven heated length *unless* the handbook itself defines the feasibility check in terms of board length (for example a "LINE SPEED (MIN) = BOARDS_PER_MIN × LENGTH_PER_BOARD / LOAD_FACTOR" rule), in which case implement that formula directly from the MES columns it names. If the handbook explicitly prints a conveyor-speed range for the applicable product/matrix row, treat that as an additional (often stricter) constraint and intersect it with any dwell-derived window.

When a question asks for a "best" run per board_family based on quality and efficiency (e.g., ranking defect/yield outcomes together with throughput), use explicit ordering rather than an ad-hoc composite: rank by (yield DESC, throughput DESC, run_id ASC) where yield is pulled from the SUMMARY stage of the defect dataset (typically `fp_yield_pct`) and throughput from the MES log (typically `boards_per_min`). The top of the ranking is best_run_id. The remaining runs for that family become runner_up_run_ids — and because the task specifies "Sort arrays by run_id or board_family or board_id ascending", that list must be serialized sorted by `run_id` ascending, not in ranked order. If the task or handbook asserts that the "best" run must be compliant (i.e., passes the ramp / TAL / peak / conveyor checks), add a `compliant DESC` sort key *before* the quality key for selecting best_run_id (the runner-up list is still emitted sorted ascending).


Here are reference codes.
```python
#Suggest to get a config object from the handbook and use it for all computations.
cfg = {
#   temperature region for the ramp calculation:
#   either {"type":"temp_band", "tmin":..., "tmax":...}
#   or {"type":"zone_band", "zones":[...]}
#   or {"type":"time_band", "t_start_s":..., "t_end_s":...}
#   "preheat_region": {...},
#   "ramp_limit_c_per_s": ...,
#   "tal_threshold_c_source": "solder_liquidus_c",   # if MES provides it
#   "tal_min_s": ...,
#   "tal_max_s": ...,
#   "peak_margin_c": ...,
#   conveyor feasibility can be many forms; represent as a rule object
}
runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))

runs["run_id"] = runs["run_id"].astype(str)
tc["run_id"]   = tc["run_id"].astype(str)
tc["tc_id"]    = tc["tc_id"].astype(str)

runs = runs.sort_values(["run_id"], kind="mergesort")
tc   = tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")
```

```python
#Always sort samples by time before any computation in thermocouple computation. Ignore segments where `dt <= 0`
df_tc = df_tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")
```

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
            total += (t1 - t0)
            continue
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

```python
# Per-run reduction across TCs (max metric, e.g. ramp)
per_tc = {}
for tc_id, g_tc in df_run.groupby("tc_id"):
    per_tc[tc_id] = max_slope_in_temp_band(g_tc, tmin, tmax)
items = [(v, tid) for tid, v in per_tc.items() if v is not None]
if items:
    items.sort(key=lambda vt: (-vt[0], vt[1]))   # value DESC, tc_id ASC
    value, chosen_tc = items[0]
else:
    value, chosen_tc = None, None
```

```python
# Per-run reduction across TCs (min metric, e.g. min peak / worst-case TAL)
per_tc = {tc_id: float(g_tc["temp_c"].max()) for tc_id, g_tc in df_run.groupby("tc_id")}
if per_tc:
    chosen_tc, value = min(per_tc.items(), key=lambda kv: (kv[1], kv[0]))  # value ASC, tc_id ASC
else:
    chosen_tc, value = None, None
```
