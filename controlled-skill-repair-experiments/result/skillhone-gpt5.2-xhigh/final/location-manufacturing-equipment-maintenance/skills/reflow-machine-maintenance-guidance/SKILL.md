---
name: reflow-machine-maintenance-guidance
description: This skill should be considered when you need to answer reflow machine maintenance questions or provide detailed guidance based on thermocouple data, MES data or defect data and reflow technical handbooks. This skill covers how to obtain important concepts, calculations, definitions, thresholds, and others from the handbook and how to do cross validations between handbook and datasets.
---

This skill should be considered when you need to answer reflow equipment maintenance questions based on thermocouple data, MES data, defect data, and reflow technical handbooks. Based on the questions, first retrieve related info from the handbook and corresponding datasets. Most frequently asked concepts include preheat, soak, reflow, cooling, ramp, slope, C/s, liquidus and wetting time, ramp rate guidance, time above liquidus, TAL, peak temperature guidance, minimum peak, margin above liquidus, conveyor speed, dwell time, heated length, zone length, time-in-oven, thermocouple placement, cold spot, worst case, representative sensor, numeric limits, temperature regions, etc. If the handbook provides multiple values or constraints, implement all and use the stricter constraint or the proper value.

Common equations used in manufacturing reflow machines include the max ramp as `max(s_i)` over the region, where `s_i = (T_i - T_{i-1}) / (t_i - t_{i-1})` for `dt > 0`.

**Important region-filter detail (avoid under-counting ramps):**
- For a temperature-band region `[tmin, tmax]`, include any segment that **overlaps** the band (do not require both endpoints to be inside the band), e.g. `max(T0,T1) >= tmin and min(T0,T1) <= tmax`.

For other region types:
- Zone band region: only consider `zone_id in zones`.
- Time band region: only consider `t_start_s <= time_s <= t_end_s`.

For wetting/TAL-type metrics, compute time above a threshold `thr` using segment interpolation.

Per-TC and run-level reductions:
- For each TC, `peak_tc = max(temp_c)`.
- Run-level coldest peak: `min_peak_run = min(peak_tc)` (tie → smallest `tc_id`).
- Peak requirement may be `required_peak = liquidus + peak_margin` and/or an absolute minimum; use handbook.

Conveyor feasibility:
- Given heated length `L_eff_cm`, minimum dwell `t_min_s`: `speed_max_cm_min = (L_eff_cm * 60) / t_min_s`.
- Given `L_eff_cm`, maximum time `t_max_s`: `speed_min_cm_min = (L_eff_cm * 60) / t_max_s`.

When reducing multiple thermocouples to one run-level result:
- If selecting a **maximum** metric, choose `(max_value, smallest_tc_id)`.
- If selecting a **minimum** metric, choose `(min_value, smallest_tc_id)`.


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
    """Max ramp (°C/s) over a temperature band.

    Do NOT require both endpoints to be inside the band.
    Include any segment that overlaps [tmin, tmax]; otherwise steep ramps that
    cross into/out of the band between samples can be missed.
    """
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    best = None
    for i in range(1, len(g)):
        dt = t[i] - t[i-1]
        if dt <= 0:
            continue
        y0, y1 = y[i-1], y[i]
        overlaps = (max(y0, y1) >= tmin) and (min(y0, y1) <= tmax)
        if overlaps:
            s = (y1 - y0) / dt
            best = s if best is None else max(best, s)
    return best  # None if no valid segments
```

```python
def time_above_threshold_s(df_tc, thr, inclusive=True):
    """Time above a temperature threshold with linear interpolation.

    Use handbook definition for inclusive vs exclusive threshold.
    """
    def is_above(v):
        return (v >= thr) if inclusive else (v > thr)

    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    total = 0.0

    for i in range(1, len(g)):
        t0, t1 = t[i-1], t[i]
        y0, y1 = y[i-1], y[i]
        if t1 <= t0:
            continue

        a0, a1 = is_above(y0), is_above(y1)

        if a0 and a1:
            total += (t1 - t0)
            continue

        crosses = (y0 < thr < y1) or (y1 < thr < y0) or (y0 == thr and y1 != thr) or (y1 == thr and y0 != thr)
        if crosses and (y1 != y0):
            frac = (thr - y0) / (y1 - y0)
            tcross = t0 + frac * (t1 - t0)
            if (not a0) and a1:
                total += (t1 - tcross)
            elif a0 and (not a1):
                total += (tcross - t0)

    return total
```
