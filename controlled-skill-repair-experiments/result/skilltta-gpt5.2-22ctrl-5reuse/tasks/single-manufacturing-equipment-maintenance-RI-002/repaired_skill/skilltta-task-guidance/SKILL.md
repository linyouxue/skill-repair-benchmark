---
name: skilltta-task-guidance
---

# Reflow Profile Compliance Toolkit — Task Guidance Skill

This skill describes a **reusable, non-hallucinating** workflow to answer reflow-process compliance questions using:
- `/app/data/handbook.pdf` (source of *definitions, equations, limits*)
- `/app/data/thermocouples.csv` (time–temperature traces)
- `/app/data/mes_log.csv` (run parameters like conveyor speed, recipe)
- `/app/data/test_defects.csv` (quality outcomes)

The outputs must be written to `/app/output/q01.json` … `/app/output/q05.json` with correct sorting, rounding, and null handling.

---

## 0) Non-hallucination rule (hard requirement)
1. **All numeric thresholds/limits/definitions must come from the handbook**.
2. If a required value cannot be found in the handbook or data files, write `null` (and mark run as failing when explicitly required, e.g., Q3 missing thermocouple data).
3. Never invent “typical” SMT values.

---

## 1) Load data deterministically
Use pandas and strict typing.

### 1.1 Read CSVs
- `thermocouples.csv`: expect columns like `run_id`, `tc_id`, `time_s` (or timestamp), `temp_c`.
- `mes_log.csv`: expect run-level settings, especially conveyor speed (units must be checked).
- `test_defects.csv`: expect `run_id`, `board_family`/`board_id`, defect counts/yield fields.

### 1.2 Normalize
- Strip whitespace in IDs: `run_id`, `tc_id`, `board_family`.
- Ensure `time_s` is numeric and sorted within each `(run_id, tc_id)`.
- Deduplicate exact duplicate rows (same run, tc, time, temp).

### 1.3 Sorting and rounding (output contract)
- Sort keys/arrays by ascending `run_id` (and `board_family`, `board_id` when required).
- Round floats to **2 decimals** at output time.

---

## 2) Extract handbook definitions, equations, and limits

### 2.1 Extract text from PDF
Use a PDF text extractor (e.g., `pdfplumber`) and keep page references.

### 2.2 Locate required clauses by keyword search
Search for (case-insensitive):
- **Preheat** definition and its temperature window (e.g., “from X°C to Y°C”, or “ambient to soak start”).
- **Ramp rate** equation and allowable limit (e.g., `°C/s` max).
- **Liquidus temperature** (solder alloy) and **TAL** definition (time above liquidus) + min/max threshold.
- **Peak temperature** requirement (min and/or max) and which thermocouple is used.
- **Conveyor speed** feasibility: board geometry, heated length, required dwell time/window, allowed speed range or formula.

### 2.3 Represent data as a parameter dictionary
Create a structured dict (all `null` until proven by handbook):
- `preheat_start_c`, `preheat_end_c`
- `ramp_rate_limit_c_per_s`
- `liquidus_temp_c`
- `tal_min_s`, `tal_max_s`
- `peak_min_c` (and peak max if specified)
- `dwell_min_s`/`dwell_target_s` and geometry constants needed for speed

If multiple handbook sections conflict, pick the one explicitly labeled as **standard**, **process spec**, or **production requirement**; otherwise keep `null` and avoid compliance claims.

---

## 3) Thermocouple “representative TC” selection (critical for Q01–Q03)

The handbook may explicitly state which TC is “representative” (e.g., “use TC at the coldest location / largest thermal mass / BGA center”).

### 3.1 First-choice: explicit handbook instruction
If the handbook specifies a particular `tc_id` (or a location mapping that can be tied to a `tc_id`), use it.

### 3.2 If handbook specifies a *principle* (common in reflow specs)
Apply principle-driven selection **after computing the metric for each TC**.

- **For Peak temperature compliance (Q03):** select the thermocouple with the **smallest peak temperature** (coldest peak) when the requirement is a minimum peak.
- **For Preheat ramp rate (Q01):** select the thermocouple with the **largest max ramp rate** when the requirement is a maximum ramp.

- **For TAL (Q02):** because TAL commonly has **both** a minimum and maximum requirement, the “worst-case” thermocouple depends on which bound is violated:
  1. Compute `tal_s` for each TC in the run.
  2. If any TC violates the **minimum** TAL (`tal_s < tal_min_s`), report the **minimum TAL** TC (shortest wetting).
  3. Else if any TC violates the **maximum** TAL (`tal_s > tal_max_s`), report the **maximum TAL** TC (longest exposure).
  4. Else (all within bounds): if the handbook names a representative location for reporting, use it; otherwise report the **minimum TAL** TC deterministically.

This prevents selecting a “representative” TC that appears compliant while another TC violates the handbook.

### 3.3 If neither explicit TC nor principle is in the handbook
Return `null` for `tc_id` selection-dependent fields or report the metric per TC internally but choose a deterministic conservative default **only if** the handbook does not contradict it. Prefer `null` over guessing.

---

## 4) Q01 — Maximum temperature ramp rate during preheat

### 4.1 Handbook-driven definition
From handbook, determine:
- What “preheat” means (segment boundary by temperature and/or time)
- Applicable temperature window (e.g., `Tstart` to `Tend`)
- Ramp calculation equation (typically `dT/dt`, in `°C/s`)
- Allowable ramp limit

### 4.2 Compute ramp rate per TC
For each `(run_id, tc_id)`:
1. Filter samples to the handbook-defined preheat window.
   - If defined by temperature: keep points where `preheat_start_c <= temp_c <= preheat_end_c`.
   - If defined by time markers that you can’t compute from available data, set result to `null`.
2. Compute instantaneous slope between adjacent points:
   - `ramp_i = (T[i+1] - T[i]) / (t[i+1] - t[i])`
   - Guard: if `Δt <= 0`, skip that segment.
3. `max_preheat_ramp_c_per_s = max(ramp_i)` over preheat segments.

### 4.3 Select representative TC for the run
Use the representative TC policy in Section 3.

### 4.4 Violations
A run violates if:
- `max_preheat_ramp_c_per_s > ramp_rate_limit_c_per_s` and both are non-null.

### 4.5 Output: `/app/output/q01.json`
```json
{
  "ramp_rate_limit_c_per_s": 0.00,
  "violating_runs": ["R0001"],
  "max_ramp_by_run": {
    "R0001": {"tc_id": "TC3", "max_preheat_ramp_c_per_s": 1.23}
  }
}
```

---

## 5) Q02 — Time Above Liquidus (TAL)

### 5.1 Handbook-driven TAL definition
Extract from handbook:
- Liquidus temperature `Tliq` (for solder alloy used)
- TAL measurement definition and comparison operator: is it `temp > Tliq` or `temp >= Tliq`?
- TAL measurement method: does it require threshold-crossing interpolation?
- Required min and max TAL thresholds

### 5.2 Compute TAL per TC
For each `(run_id, tc_id)`:
1. Identify all time intervals where the trace is above liquidus according to the handbook operator (`>` vs `>=`).
2. Compute total time above liquidus using the handbook’s stated method.
   - If the handbook is silent on crossing measurement, use a deterministic default (linear interpolation at crossings) and document that it was used because the handbook did not contradict it.
3. Result `tal_s`.

### 5.3 Select the reported TC and compute run-level status (do not hide violations)
Because the output requires a single record per run, you must (unless the handbook explicitly defines otherwise):

- Evaluate compliance across **all** TCs for the run.
- If any TC violates `tal_min_s`, report the TC with **minimum** `tal_s` and mark `non-compliant`.
- Else if any TC violates `tal_max_s`, report the TC with **maximum** `tal_s` and mark `non-compliant`.
- Else report the handbook-specified representative TC; if none is specified, report the minimum `tal_s` TC deterministically and mark `compliant`.

If a run has no TC data, set `tc_id=null`, `tal_s=null`, and `status=non-compliant`.

### 5.4 Output: `/app/output/q02.json`
Array sorted by `run_id`.

---

## 6) Q03 — Peak temperature requirement

### 6.1 Handbook requirements
Extract required minimum peak (and maximum if specified). Also extract which TC to use.

### 6.2 Compute peak per TC
For each `(run_id, tc_id)`: `peak_temp_c = max(temp_c)`.

### 6.3 Representative TC selection
Follow handbook. If handbook uses coldest location for qualification, select **minimum peak** TC (Section 3.2).

### 6.4 Run failing conditions
- If a run has **no thermocouple data**: failing (explicit requirement).
- If peak requirement exists and selected peak is below min (or above max if applicable): failing.

### 6.5 Output: `/app/output/q03.json`
- `failing_runs`: sorted list.
- `min_peak_by_run`: store the representative/worst-case TC id, peak, and required minimum peak.

---

## 7) Q04 — Conveyor speed feasibility

### 7.1 Handbook geometry + dwell model
From handbook, extract:
- Board geometry / effective heated length model (e.g., “board length + margin” or “zone length”).
- Required thermal dwell time (or constraint like “time in reflow zone must be between A and B seconds”).
- Allowed conveyor speed range or equation:
  - Typical form: `speed = effective_length / dwell_time` with unit conversions.

### 7.2 Get actual speed from MES logs
- Parse `mes_log.csv` for conveyor speed per `run_id`.
- Confirm units from handbook/MES header. Convert to `cm/min` for output.

### 7.3 Compute required minimum speed
Example pattern (must match handbook’s formula):
- If handbook provides **max dwell time**, then you need **min speed**: `min_speed = effective_length / max_dwell`.
- If handbook provides **min dwell time**, then you need **max speed**: `max_speed = effective_length / min_dwell`.
This task asks specifically for `required_min_speed_cm_min`—derive it accordingly from the handbook’s dwell constraint.

### 7.4 Meets
`meets = (actual_speed_cm_min >= required_min_speed_cm_min)` when both known; else `false`.

### 7.5 Output `/app/output/q04.json`
Array sorted by `run_id`.

---

## 8) Q05 — Best run per board_family (quality + efficiency)

### 8.1 Join datasets
- Map `run_id -> board_family` from `test_defects.csv` (or MES if needed).
- Bring in compliance outcomes from Q01–Q04 computations (do not re-infer).

### 8.2 Define “quality” and “efficiency” using only available data
Do not invent metrics:
- Quality: defect count, defect rate, pass/fail status fields present in `test_defects.csv`.
- Efficiency: conveyor speed or cycle time proxies available in `mes_log.csv`.

### 8.3 Selection rule (deterministic)
For each `board_family`:
1. Prefer runs that are compliant on critical thermal metrics (TAL, peak, ramp, speed) when those requirements exist in handbook.
2. Among remaining, choose the run with best quality (e.g., lowest defect rate). Use a clear tie-breaker.
3. If still tied, choose higher efficiency (e.g., higher conveyor speed within allowed range).
4. Final tie-breaker: smallest `run_id`.

Output `runner_up_run_ids` as the remaining run_ids for that board_family (sorted).

---

## 9) Output writing
- Ensure `/app/output/` exists.
- Write strict JSON.
- Convert NaN to null.
- Round floats to 2 decimals.

---

## 10) Common edge cases checklist
- Missing handbook parameters → output nulls, avoid compliance claims.
- Thermocouple time not monotonic → sort by time; drop non-increasing segments for slope.
- Sparse data in preheat window → ramp becomes null.
- TAL crossing occurs between samples → interpolate if handbook demands; if handbook is silent, use deterministic interpolation and document.
- A run present in MES but absent in TC data → fails Q03 per requirement.

---
