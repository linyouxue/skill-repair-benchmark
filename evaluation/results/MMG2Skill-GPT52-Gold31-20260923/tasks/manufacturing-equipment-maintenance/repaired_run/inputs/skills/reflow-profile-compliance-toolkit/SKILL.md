---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval and thermocouple computations
  for ramp, TAL, peak, conveyor feasibility, and best-run selection; includes tooling/IO
  guardrails so outputs get generated.
---

## Steps
1. **Tool/terminal execution discipline (mandatory):**
   - If the terminal tool allows only one command per call, either (a) run one command per call, or (b) chain sub-commands into a *single* shell line using `&&` or `;`.
   - Prefer robust one-liners (example pattern): `cmd1 && cmd2 && cmd3`.
2. Enumerate and validate inputs:
   - `ls -lah /app/data`
   - preview schemas with `python -c` or `head` to confirm required columns exist (especially `thermocouples.csv: run_id, tc_id, time_s, temp_c`).
3. Extract handbook requirements into `cfg` (do not compute until this is filled from the handbook text):
   ```python
   cfg = {
     "preheat_region": {...},
     "ramp_limit_c_per_s": ...,
     "tal_threshold_c_source": "solder_liquidus_c",
     "tal_min_s": ...,
     "tal_max_s": ...,
     "peak_margin_c": ...,
     "conveyor_rule": {...},
   }
   ```
4. Prepare data deterministically:
   - cast `run_id`, `tc_id` to string;
   - sort `thermocouples.csv` by `run_id, tc_id, time_s` (stable mergesort).
5. Compute metrics using the canonical recipes:
   - ramp: finite difference `s_i = (T_i - T_{i-1})/(t_i - t_{i-1})`, max over the handbook-defined preheat region (temperature/zone/time band as specified);
   - TAL: `time_above_threshold_s(df_tc, liquidus_c)` using linear interpolation and the handbook’s TAL window definition;
   - peak: per-TC `max(temp_c)`, then run-level “coldest”/representative selection per handbook; if a run has no TC data, mark failing.
6. Build outputs with JSON guardrails:
   - sort arrays/dict keys by ID ascending;
   - round to 2 decimals;
   - replace missing/invalid numeric results with `null`;
   - never claim compliance when the metric is `null` unless the handbook explicitly allows it.
7. **Write, then verify**: create `/app/output` if needed, write each required JSON file, and confirm existence and valid JSON parse before responding.
## Expected Result
A single coherent workflow that (1) successfully extracts handbook limits/definitions, (2) computes ramp/TAL/peak/speed feasibility deterministically from thermocouple traces, and (3) writes and verifies `/app/output/q01.json`–`/app/output/q05.json` without terminal/tool-call formatting failures or premature termination.
