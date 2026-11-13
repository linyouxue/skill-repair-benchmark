---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval + thermocouple computations
  for reflow profile compliance outputs (ramp, TAL, peak, feasibility, best-run selection)
  with stable sensor-selection rules.
---

## Steps
1. From the task questions, list the required handbook items to extract (definitions, regions/windows, numeric limits, and **thermocouple “representative/cold-spot” selection** guidance).
2. Search **handbook.pdf** for these sections/tables and extract a compact `cfg` used by all computations:
   - Thermal profile overview: “preheat”, “soak”, “reflow”, “cooling”
   - Ramp/slope guidance: “°C/s”
   - Liquidus & TAL/wetting time: “liquidus”, “time above liquidus”, “TAL”, “wetting”
   - Peak guidance: “minimum peak”, “margin above liquidus”
   - Conveyor/dwell feasibility: “conveyor speed”, “dwell time”, “heated length”, “time-in-oven”
   - Thermocouple placement: “cold spot”, “representative sensor”
   ```python
   cfg = {
     "preheat_region": {...},      # temp_band / zone_band / time_band
     "ramp_limit_c_per_s": ...,
     "tal_threshold_c_source": "solder_liquidus_c",
     "tal_min_s": ...,
     "tal_max_s": ...,
     "peak_margin_c": ...,
     "conveyor_rule": {...},
   }
   ```
3. Load `/app/data/mes_log.csv` and `/app/data/thermocouples.csv`, coerce `run_id`/`tc_id` to strings, and sort deterministically (stable `mergesort`). Always sort TC samples by `time_s` before any calculation and ignore segments where `dt <= 0`.
4. Compute thermocouple metrics using deterministic recipes:
   - **Max ramp** in the handbook-defined preheat region: finite-difference slope on consecutive samples, filtered to the region.
   - **TAL**: time at-or-above the liquidus threshold using linear interpolation at crossings (do not “count samples”).
   - **Peak** per TC: `max(temp_c)`.
   Use reference implementations (same logic for all runs/TCs):
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
       return best
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
           elif (a0 != a1) and (y1 != y0):
               frac = (thr - y0) / (y1 - y0)
               tcross = t0 + frac * (t1 - t0)
               total += (tcross - t0) if a0 else (t1 - tcross)
       return total
   ```
5. Apply **fixed, handbook-driven representative thermocouple selection** (deterministic; do not switch rules based on whether a run violates):
   - **Q01 ramp:** select the TC with **maximum** preheat ramp; tie-break by smallest `tc_id`.
   - **Q02 TAL:** select the handbook’s **representative / cold-spot** thermocouple for TAL reporting. If the handbook does not map directly to a labeled TC in the data, operationalize “cold spot” as the TC with **minimum peak temperature** in that run; tie-break by smallest `tc_id`. Report **that TC’s** `tal_s` and compute status from it versus the handbook TAL window.
   - **Q03 peak:** select the TC with **minimum peak temperature**; tie-break by smallest `tc_id`.
6. Build outputs with strict completeness and determinism:
   - **Q02 deliverable rule:** emit **one record per `run_id` in MES**, even if a run has no thermocouple rows (`tc_id: null`, `tal_s: null`, `status: non-compliant`).
   - Sort arrays lexicographically by `run_id` (and other keys as specified).
   - Round floats to 2 decimals; replace missing/invalid/NaN/Inf with `null`.
   ```python
   def r2(x):
       if x is None:
           return None
       if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
           return None
       return float(round(float(x), 2))
   ```
7. Treat the task as complete only after writing the required JSON outputs under `/app/output` and verifying:
   - files exist and `json.load()` parses them
   - Q02 row count matches the number of MES runs (coverage check)
   - no NaN/Inf values remain after rounding/nulling
   - sensor selection tie-breaks are stable and documented in code comments

## Expected Result
A reproducible, handbook-auditable pipeline that (1) extracts limits/windows from the handbook, (2) computes ramp/TAL/peak using deterministic segment math and interpolation, (3) selects a **fixed representative/cold-spot TC for Q02** rather than “all-TC” or violation-direction switching, and (4) writes complete, correctly-sorted JSON outputs for every run.
