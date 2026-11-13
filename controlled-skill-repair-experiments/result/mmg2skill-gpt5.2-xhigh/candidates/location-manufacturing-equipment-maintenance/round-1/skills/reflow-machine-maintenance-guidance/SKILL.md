---
name: reflow-machine-maintenance-guidance
description: Answer reflow equipment maintenance / process-compliance questions using
  handbook-grounded definitions plus deterministic computations from MES logs, thermocouple
  traces, and defect data.
---

## Steps
1. Identify which handbook-defined items the question depends on (e.g., **preheat definition and temperature band**, ramp equation and limit, **liquidus temperature**, **TAL definition and window**, peak margin above liquidus, conveyor/dwell feasibility rules, and any **representative / cold-spot thermocouple** guidance).
2. Open **handbook.pdf** and extract the needed definitions/limits into a small `cfg` object. If multiple constraints apply, keep them and use the stricter/applicable one (leave an audit note in code comments).
3. Load relevant datasets from `/app/data` and normalize IDs/types; then sort deterministically (stable sort):
   ```python
   cfg = {
   #   "preheat_region": {...},          # temp_band / zone_band / time_band
   #   "ramp_limit_c_per_s": ...,
   #   "tal_threshold_c_source": "solder_liquidus_c",  # if MES provides it
   #   "tal_min_s": ...,
   #   "tal_max_s": ...,
   #   "peak_margin_c": ...,
   #   "conveyor_rule": {...},
   }

   runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
   tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))

   runs["run_id"] = runs["run_id"].astype(str)
   tc["run_id"]   = tc["run_id"].astype(str)
   tc["tc_id"]    = tc["tc_id"].astype(str)

   runs = runs.sort_values(["run_id"], kind="mergesort")
   tc   = tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")
   ```
4. Compute thermocouple metrics deterministically (always sort by `time_s`; ignore segments where `dt <= 0`):
   - **Ramp / slope:** `s = (T_i - T_{i-1}) / (t_i - t_{i-1})` for `dt > 0`, filtered to the handbook region (temp band / zones / time band).
   - **TAL / wetting time:** time at-or-above the liquidus threshold using linear interpolation at crossings.
   - **Peak:** `peak_tc = max(temp_c)` per TC.
   - **Conveyor feasibility:** derive speeds from handbook dwell/length formulas as applicable.

   Reference implementations:
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

           a0 = (y0 >= thr)
           a1 = (y1 >= thr)

           if a0 and a1:
               total += (t1 - t0)
               continue

           if (a0 != a1) and (y1 != y0):
               frac = (thr - y0) / (y1 - y0)
               tcross = t0 + frac * (t1 - t0)
               total += (tcross - t0) if a0 else (t1 - tcross)
       return total
   ```
5. Reduce multi-thermocouple data to one run-level result **using the handbook’s representative/worst-case rule** for that metric, with deterministic ties:
   - If selecting a **maximum-type** metric (e.g., max ramp): choose `(max_value, smallest_tc_id)`.
   - If selecting a **minimum-type** metric (e.g., cold-spot peak/TAL): choose `(min_value, smallest_tc_id)`.
6. Build JSON outputs with sorted IDs and 2-decimal rounding; emit `null` for missing/invalid values (never `NaN/Inf`). Do a quick coverage check that every expected `run_id` appears, and re-load written JSONs to confirm they parse.

## Expected Result
Handbook-grounded, reproducible calculations and compliant JSON outputs that are deterministic (stable sorting, stable tie-breaks, interpolation for TAL) and complete (coverage across runs with `null` where necessary).
