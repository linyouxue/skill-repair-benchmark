# Reflow Machine Maintenance Guidance

## Purpose
Answer reflow-oven maintenance questions by combining a technical handbook (PDF) with MES, thermocouple, and defect CSVs, then emit one JSON answer file per question into the task-specified output directory. Compute numerical metrics with the provided helpers; use the handbook for thresholds and definitions, and cross-validate against the data.

## When to Use
The task prompt poses one or more reflow-oven questions (ramp, soak, TAL, peak margin, conveyor speed, dwell, zone/time/temp bands, defect correlation) and supplies a handbook PDF plus CSV datasets. Each question expects a structured JSON artifact at a verifier-visible path.

## Procedure
- Discover and validate inputs.
- List the task data directory and output directory. Identify the handbook PDF, `mes_log.csv`, `thermocouples.csv`, and any defect file. Identify the question list (prompt, enumerated files, or questions.json).
- Evidence: printed file listing and a line per question id to answer.
- If a required dataset is missing, record it and continue to still answer handbook-only questions.
- Extract the handbook with a fallback chain.
- Try in order: `pdfplumber`, `pypdf`, `PyPDF2`, `fitz` (PyMuPDF), shell `pdftotext`. Stop at the first that returns non-empty text.
- Evidence: print the extractor used and the first ~500 characters.
- If all fail, log `handbook_extract: unavailable` and proceed; set handbook-derived fields to `null` rather than guessing.
- Build a config object from the handbook.
- Populate only keys the questions require, e.g. `preheat_region` ({type: temp_band|zone_band|time_band, ...}), `ramp_limit_c_per_s`, `solder_liquidus_c`, `tal_min_s`, `tal_max_s`, `peak_margin_c`, `L_eff_cm`, `dwell_min_s`, `dwell_max_s`.
- If the handbook gives multiple values or ranges, keep the stricter constraint.
- Evidence: print the resolved config dict; any unparseable value is `null`.
- Load and normalize datasets.
- Cast `run_id`, `tc_id` to str. Sort `tc` by `(run_id, tc_id, time_s)` with mergesort. Sort `runs` by `run_id`.
- Ignore any time segment where `dt <= 0`.
- Compute per question using the helpers below.
- Max ramp in a region: use `max_slope_in_temp_band` (or analogous zone/time filters) requiring both endpoints inside the region.
- TAL / wetting: `time_above_threshold_s` with linear interpolation at crossings.
- Peak per run: `peak_tc = max(temp_c)` per TC; `min_peak_run = min(peak_tc)`; `required_peak = liquidus + peak_margin`.
- Conveyor feasibility: `speed_max_cm_min = (L_eff_cm / dwell_min_s) * 60`; `speed_min_cm_min = (L_eff_cm / dwell_max_s) * 60`.
- Run-level reduction across TCs: for a max metric pick `(max_value, smallest tc_id)`; for a min metric pick `(min_value, smallest tc_id)`.
- Write one JSON file per question to the task-specified output directory.
- Use the filename pattern the task prompt declares (e.g. `q01.json`); do not invent names.
- Include exactly the keys the question asks for. Use `null` (not strings) for unknown numerics. Round only if the question specifies rounding.
- Verify before terminating.
- Re-list the output directory. For each expected question id, assert the file exists and `json.loads` succeeds and required keys are present with correct types.
- If any file is missing or invalid, fix and rewrite; do not end the turn until every expected `qNN.json` is present and parses. ## Reference helpers ```python def max_slope_in_temp_band(df_tc, tmin, tmax): g = df_tc.sort_values("time_s") t = g["time_s"].to_numpy(float); y = g["temp_c"].to_numpy(float) best = None for i in range(1, len(g)): dt = t[i] - t[i-1] if dt <= 0: continue if (tmin <= y[i-1] <= tmax) and (tmin <= y[i] <= tmax): s = (y[i] - y[i-1]) / dt best = s if best is None else max(best, s) return best ``` ```python def time_above_threshold_s(df_tc, thr): g = df_tc.sort_values("time_s") t = g["time_s"].to_numpy(float); y = g["temp_c"].to_numpy(float) total = 0.0 for i in range(1, len(g)): t0,t1,y0,y1 = t[i-1],t[i],y[i-1],y[i] if t1 <= t0: continue if y0 > thr and y1 > thr: total += (t1 - t0); continue crosses = (y0 <= thr < y1) or (y1 <= thr < y0) if crosses and y1 != y0: frac = (thr - y0) / (y1 - y0) tc = t0 + frac*(t1 - t0) total += (t1 - tc) if (y0 <= thr and y1 > thr) else (tc - t0) return total ```

## Constraints / Pitfalls
- Do not terminate until every expected `qNN.json` has been written to the task output directory and successfully reloaded with `json.loads`.
- Do not fabricate handbook numbers. If extraction fails or a value is not found, emit `null` and continue; never block the entire batch on one missing parameter.
- Do not hard-code question count, filenames, output path, or thresholds; discover them from the task prompt and handbook.
- Keep per-question computation independent: a failure in one question must not prevent writing the others.
- Enforce sort-and-skip rules: sort by `(run_id, tc_id, time_s)` and skip any segment with `dt <= 0` before any slope or TAL computation.
- When the handbook gives multiple limits for the same quantity, apply the stricter one.
- Budget guard: cap discovery at a few shell/list calls; move to extraction and compute quickly to avoid exhausting the step/latency budget.