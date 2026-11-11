# reflow-profile-compliance-toolkit

## Purpose
Produce deterministic reflow-profile compliance outputs (ramp, TAL, peak, feasibility, selection) by extracting handbook limits, computing per-run thermocouple metrics, and writing one JSON artifact per question. Favor producing partial outputs over perfect ones.

## When to Use
Any task asking reflow questions grounded in a handbook PDF plus MES and thermocouple CSVs, where multiple numbered question outputs must be written to a known output directory.

## Procedure
- Discover environment: list the input directory and output directory from the task prompt (do not hard-code). Confirm expected CSV files (MES log, thermocouples) and a handbook PDF exist. If output directory is missing, create it.
- Load CSVs: read MES and thermocouple tables; cast id columns to strings; sort thermocouples by (run_id, tc_id, time_s); drop segments where dt <= 0.
- Extract handbook config with bounded fallback. Try in order: pdfplumber, pypdf, PyPDF2, then subprocess `pdftotext` or `pdfminer`. If all fail, set `cfg = {degraded: true}` with every numeric limit = null and continue. Parse limits (ramp_limit, TAL threshold/min/max, peak_margin, conveyor rule, preheat region) via regex; any field not found stays null.
- For each question qNN in order: compute its metric using the rules in Constraints; build the JSON object; write `<OUT_DIR>/qNN.json` immediately before starting the next question. Never batch all writes to the end.
- Final sweep: verify each expected `qNN.json` exists; if any is missing, write a minimal valid JSON with nulls and `status="unknown"` so no file is absent.

## Constraints / Pitfalls
- Ramp: finite-difference slope over consecutive samples; include a segment only if both endpoints lie inside the configured region (temp band, zone list, or time band). Max ramp is max over valid segments; null if none.
- Time above threshold: linear interpolation across crossings; never naive bucket counting.
- Sensor tie-breaks: for max-metric selections pick (max_value, smallest tc_id); for min-metric selections pick (min_value, smallest tc_id). Lexicographic string compare on tc_id.
- Peak and margin: per-TC peak = max(temp_c); run peak uses coldest-TC rule when handbook calls for worst case; required_peak = liquidus + peak_margin.
- Conveyor feasibility: compute `speed_min_cm_min = (L_eff_cm / t_bound_s) * 60`; if any input is null, set required speed to null and `meets=false`.
- If a cfg limit needed for a question is null (degraded extraction), emit numeric fields as null and `status` as "non_compliant" or "unknown" rather than aborting.
- Missing TC rows for a run: numeric metrics = null; include run in failing/unknown list; do not claim pass.
- Output hygiene: id fields as strings; arrays sorted lexicographically by primary id; dict keys emitted in sorted order; floats rounded to 2 decimals; replace NaN/Inf with null; valid JSON only.
- Do not spend more than a small bounded effort on handbook tool discovery; after the fallback chain fails, proceed to compute and write.
- Write each `qNN.json` the moment its computation completes, so a later failure still leaves earlier artifacts on disk.