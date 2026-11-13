---
name: reflow-machine-maintenance-guidance
description: This skill should be considered when you need to answer reflow machine maintenance questions or provide detailed guidance based on thermocouple data, MES data or defect data and reflow technical handbooks. This skill covers how to obtain important concepts, calculations, definitions, thresholds, and others from the handbook and how to do cross validations between handbook and datasets.
---

This skill should be considered when you need to answer reflow equipment maintenance questions based on thermocouple data, MES data, defect data, and reflow technical handbooks. Based on the questions, first retrieve related info from the handbook and corresponding datasets. Most frequently asked concepts include preheat, soak, reflow, cooling, ramp, slope, C/s, liquidus and wetting time, ramp rate guidance, time above liquidus, TAL, peak temperature guidance, minimum peak, margin above liquidus, conveyor speed, dwell time, heated length, zone length, time-in-oven, thermocouple placement, cold spot, worst case, representative sensor, numeric limits, temperature regions, etc. If the handbook provides multiple values or constraints, implement all and use the stricter constraint or the proper value.

Common equations used in manufacturing reflow machines include the max ramp is max(s_i) over the region, where s_i = (T_i - T_{i-1}) / (t_i - t_{i-1}) for dt > 0. For a temperature-band-defined region, include any segment that **intersects** the band (not only segments whose endpoints are both inside); if exact entry/exit times are needed for time-in-band, use linear interpolation at the band boundary. For the zone band region, only consider zone_id in zones. For time band region, only consider segments that intersect `t_start_s..t_end_s` (and clip/interpolate segment endpoints when computing time-in-window). For wetting/TAL-type metrics, compute time above a threshold `thr` using segment interpolation. For each TC, peak_tc = max(temp_c). min_peak_run = min(peak_tc), and required_peak = liquidus + peak_margin. Given heated length L_eff_cm, minimum dwell t_min_s, speed_max_cm_min = (L_eff_cm / t_min_s) * 60. Given L_eff_cm, maximum time t_max_s, speed_min_cm_min = (L_eff_cm / t_max_s) * 60. When reducing multiple thermocouples to one run-level result, first apply any handbook-stated measurement-point rule (including rules like “use the coldest spot”); otherwise reduce by compliance direction with deterministic tie-breaks: max-only limits (e.g., ramp-rate limit) ⇒ choose the **maximum** metric TC; min-only limits (e.g., minimum peak) ⇒ choose the **minimum** metric TC; window limits (e.g., TAL min/max) ⇒ if any TC violates, report the TC that violates (min TAL if below min, else max TAL if above max), otherwise report the handbook-defined representative TC (commonly the cold-spot TC such as the minimum-peak TC). Only if the handbook is silent and no compliance direction is implied, use deterministic numeric reduction with stable tie-breaks: if selecting a maximum metric choose (max_value, smallest_tc_id); if selecting a minimum metric choose (min_value, smallest_tc_id).


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
        # include any segment that intersects the band [tmin, tmax]
        if (max(y[i-1], y[i]) >= tmin) and (min(y[i-1], y[i]) <= tmax):
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
