---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval + thermocouple computations
  for reflow profile compliance outputs (ramp, TAL, peak, feasibility, best-run selection)
  with stable sensor-selection rules.
---

## Steps
1. From the task questions, list the required handbook items to extract (definitions, regions/windows, numeric limits, and **thermocouple “representative/cold-spot” selection** guidance).
2. Search **handbook.pdf** for these sections/tables and extract a compact `cfg` used by all computations. When the handbook provides both “typical/normal” values and separate “allowable/acceptance/spec” limits, use the **allowable/acceptance/spec** limits. When extracting/searching via the shell tool, run **one command per tool call** (or a single chained command with `&&`) and keep the tool command content to just the command string:
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
3. Confirm the required inputs exist under `/app/data` (e.g., `ls -l /app/data`), then load `/app/data/mes_log.csv` and `/app/data/thermocouples.csv` (and `/app/data/test_defects.csv` when ranking runs for Q05). Coerce `run_id`/`tc_id` to strings, and sort deterministically (stable `mergesort`). Always sort TC samples by `time_s` before any calculation and ignore segments where `dt <= 0`. If using MES `solder_liquidus_c` as the TAL threshold, check for missing values and handle explicitly (fallback to handbook liquidus or `null`).
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
5. Apply **fixed, handbook-driven representative thermocouple selection** (deterministic; define the rule up front and apply it uniformly):
   - **Q01 ramp:** select the TC with **maximum** preheat ramp; tie-break by smallest `tc_id`.
   - **Q02 TAL:** select the handbook’s representative TC for TAL/wetting; if the handbook indicates the “cold spot / slowest-to-reflow” point is representative, operationalize deterministically as the TC with the **minimum computed `tal_s`** in the run; tie-break by smallest `tc_id`. Compute `tal_s` for that TC and judge `"compliant"` iff `tal_min_s <= tal_s <= tal_max_s`.
   - **Q03 peak:** select the TC with **minimum peak temperature**; tie-break by smallest `tc_id`.
6. Build outputs with strict completeness and determinism:
   - Ensure `/app/output` exists and emit outputs exactly to `/app/output/q01.json` … `/app/output/q05.json`.
   - Coverage (don’t drop runs): emit results for **every `run_id` in MES** for Q01–Q04 (using `null` where needed) and for **every `board_family` in MES** for Q05.
     - **Q01:** `max_ramp_by_run` must contain each `run_id`; if no usable ramp, set `tc_id: null`, `max_preheat_ramp_c_per_s: null` (and don’t omit the run).
     - **Q02 deliverable rule:** emit **one record per `run_id` in MES**; if a run has no usable TAL computation, set `tc_id: null`, `tal_s: null`, and `status: "non-compliant"` (still populate required min/max from `cfg`).
     - **Q03:** `min_peak_by_run` must contain each `run_id`; if a run has no thermocouple data, it is failing (task requirement) and should have `tc_id: null`, `peak_temp_c: null`.
     - **Q04:** emit one record per `run_id`; if required/actual speed can’t be computed, set numeric fields `null` and `meets: false`.
   - Sort arrays lexicographically by `run_id` (and other keys as specified). For Q05, also sort each record’s `runner_up_run_ids` ascending by `run_id`.
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
   - `/app/output/q01.json` … `/app/output/q05.json` exist and `json.load()` parses them
   - Q01/Q03 maps cover all MES `run_id`s; Q02/Q04 array lengths match the number of MES runs; Q05 length matches the number of MES board families
   - no NaN/Inf values remain after rounding/nulling
   - sensor-selection tie-breaks are stable and documented in code comments

## Expected Result
A reproducible, handbook-auditable pipeline that (1) extracts limits/windows from the handbook, (2) computes ramp/TAL/peak using deterministic segment math and interpolation, (3) for Q02 uses the handbook’s **representative/cold-spot thermocouple** selection (operationalized as **minimum TAL** when the handbook indicates cold-spot evaluation), and (4) writes complete, correctly-sorted JSON outputs for every run.
