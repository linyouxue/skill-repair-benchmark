---
name: reflow-machine-maintenance-guidance
description: Use handbook-grounded definitions/limits plus thermocouple/MES/defect
  data to answer reflow maintenance & compliance questions and produce required JSON
  artifacts.
---

## Steps
1. Start by inspecting available inputs with **plain ASCII** shell flags/quotes (avoid copy/paste of malformed “-l”): list `/app/data` and preview CSV schemas (headers + first rows) to confirm required columns like `run_id`, `tc_id`, `time_s`, `temp_c`.
2. Extract the **exact** definitions and numeric requirements from `handbook.pdf` before calculating anything: preheat definition + applicable temperature/zone/time region, ramp equation, ramp limit; TAL threshold/window/min/max; peak requirement and how to choose the representative thermocouple (e.g., “cold spot”/minimum peak guidance); conveyor geometry + dwell/length rules.
3. Convert handbook content into a compact `cfg` object (regions, thresholds, limits) and use it consistently for every computation and output file.
4. Compute per-run metrics from thermocouple traces deterministically:
   - always sort by `run_id, tc_id, time_s`;
   - ignore segments with `dt <= 0`;
   - use finite-difference slope for ramp in the handbook’s defined region;
   - use linear interpolation for time-above-threshold metrics (TAL-type).
5. Reduce multiple thermocouples to run-level results using the handbook’s “representative” guidance; if the handbook is not explicit, use deterministic tie-breaks:
   - max-type metric ⇒ pick max value, then smallest `tc_id`;
   - min-type (“coldest”) metric ⇒ pick min value, then smallest `tc_id`.
6. Write the required outputs to `/app/output/q01.json` … `/app/output/q05.json`, rounding floats to 2 decimals, sorting by IDs ascending, and emitting `null` where data/segments are missing (do not guess).
7. Before finishing, verify that all `/app/output/q0*.json` files exist and contain valid JSON (no NaN/Inf).
## Expected Result
Handbook-backed calculations are performed end-to-end and the five required JSON files are actually written under `/app/output/`, with deterministic sensor selection, correct rounding/sorting, and no hallucinated values.
