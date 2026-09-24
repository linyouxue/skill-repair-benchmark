---
name: reflow-machine-maintenance-guidance
description: This skill should be considered when you need to answer reflow machine maintenance questions or provide detailed guidance based on thermocouple data, MES data or defect data and reflow technical handbooks. This skill covers how to obtain important concepts, calculations, definitions, thresholds, and others from the handbook and how to do cross validations between handbook and datasets.
---

This skill should be considered when you need to answer reflow equipment maintenance questions based on thermocouple data, MES data, defect data, and reflow technical handbooks. Based on the questions, first retrieve related info from the handbook and corresponding datasets. Most frequently asked concepts include preheat, soak, reflow, cooling, ramp, slope, C/s, liquidus and wetting time, ramp rate guidance, time above liquidus, TAL, peak temperature guidance, minimum peak, margin above liquidus, conveyor speed, dwell time, heated length, zone length, time-in-oven, thermocouple placement, cold spot, worst case, representative sensor, numeric limits, temperature regions, etc. If the handbook provides multiple values or constraints, implement all and use the stricter constraint or the proper value.
Representative-thermocouple convention (very important):
- The handbook's "most representative thermocouple" is generally the **largest-thermal-mass** location (the coldest / slowest-heating sensor). Reflow profiling convention: the largest-mass TC is the worst case for TAL and peak (it lags the profile), and is also the canonical sensor for ramp reporting because if the coldest point meets the limit, all points do.
- Practical selection rule: prefer the TC whose `tc_location` matches `largest_mass` (or the closest synonym: `large_mass`, `thermal_mass`, `heaviest`, `component_body_large`). If no such label exists, fall back to the TC with the **lowest peak temperature** in that run (deterministic proxy for largest mass = coldest).
- Apply this same representative-TC selection consistently across Q1 (ramp), Q2 (TAL), and Q3 (peak). Do NOT use "max across TCs" for ramp or "min across TCs" for TAL/peak as independent heuristics — pick the representative TC first, then report that TC's metric.
- Tie-break when multiple TCs share the representative label: smallest `tc_id` lexicographically.
Common equations used in manufacturing reflow machines include the max ramp is max(s_i) over the region, where s_i = (T_i - T_{i-1}) / (t_i - t_{i-1}) for dt > 0. For the temperature band region, only consider segments where both endpoints satisfy tmin <= T <= tmax. For the zone band region, only consider zone_id in zones. For time band region, only consider t_start_s <= time_s <= t_end_s. For wetting/TAL-type metrics, compute time above a threshold `thr` using segment interpolation. For each TC, peak_tc = max(temp_c). required_peak = liquidus + peak_margin. Peak is per the representative TC (see rule above). If a run has no TC data, it fails Q3.
Conveyor-speed feasibility (Q4): derive the constraint from the **oven heated length** and the handbook TAL/dwell window, NOT from board length alone.
- Let `L_heated_cm` = heated (reflow-zone or total heated) length from the handbook.
- Let `t_tal_max_s` = max TAL from the handbook (upper dwell bound above liquidus).
- Then `required_min_speed_cm_min = (L_heated_cm / t_tal_max_s) * 60` (going slower would exceed max TAL).
- Also compute `required_max_speed_cm_min = (L_heated_cm / t_tal_min_s) * 60` if a min-TAL bound exists, and check the actual speed lies within `[required_min, required_max]` and also within the handbook's absolute allowable conveyor-speed range.
- The Q4 schema only asks for `required_min_speed_cm_min`; still verify against both bounds internally and set `meets=false` if either is violated.
Best-run selection (Q5) must combine **quality and efficiency AND compliance**:
- First filter out runs that fail Q1 (ramp), Q2 (TAL), Q3 (peak), or Q4 (conveyor). Only compliant runs are eligible to be `best_run_id`.
- Rank eligible runs by `fp_yield_pct` desc, then `boards_per_min` desc, tie-break by `run_id` asc.
- `runner_up_run_ids` = all other run_ids in that board_family (compliant or not) except the best, sorted by run_id asc.
- If no run in a board_family is compliant, pick the best by yield/throughput anyway and note the situation.
Here are reference codes.
```python
#Suggest to get a config object from the handbook and use it for all computations.
cfg = {
#   "preheat_region": {"type":"temp_band", "tmin":100, "tmax":150},
#   "ramp_limit_c_per_s": 2.0,
#   "tal_threshold_c_source": "solder_liquidus_c",
#   "tal_min_s": 30, "tal_max_s": 60,
#   "peak_margin_c": 20,
#   "heated_length_cm": ...,   # from handbook
#   "conveyor_speed_min_cm_min": ..., "conveyor_speed_max_cm_min": ...,
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
# Select representative TC for a run: prefer largest_mass label; fallback to lowest peak.
def select_representative_tc(df_run):
    labels = df_run[["tc_id","tc_location"]].drop_duplicates()
    mass_synonyms = ["largest_mass","large_mass","thermal_mass","heaviest","big_mass"]
    cand = labels[labels["tc_location"].str.lower().isin(mass_synonyms)]
    if len(cand):
        return sorted(cand["tc_id"].tolist())[0]
    # fallback: lowest peak per TC, then smallest tc_id
    peaks = df_run.groupby("tc_id")["temp_c"].max().reset_index()
    peaks = peaks.sort_values(["temp_c","tc_id"], kind="mergesort")
    return peaks.iloc[0]["tc_id"]
```
