---
name: skilltta-task-guidance
---

# Reflow Profile Compliance Toolkit — Task Guidance (Temporary Skill)

This skill describes a repeatable, non-hallucinatory workflow to answer Q01–Q05 using only:

- `/app/data/handbook.pdf`
- `/app/data/thermocouples.csv`
- `/app/data/mes_log.csv`
- `/app/data/test_defects.csv`

Outputs must be written exactly to:

- `/app/output/q01.json`
- `/app/output/q02.json`
- `/app/output/q03.json`
- `/app/output/q04.json`
- `/app/output/q05.json`

All numeric floats in outputs must be **rounded to 2 decimals**. Arrays must be **sorted ascending** as required.

---

## 0) Hard rules (do not violate)

1. **Never guess handbook limits or temperature regions.** If a needed parameter cannot be found in the handbook text, set it to `null` and propagate `null` outputs that depend on it.
2. **Never “assume” liquidus, peak limits, preheat definitions, etc.** They must be extracted from the handbook.
3. **Representative thermocouple selection must follow the handbook.** If the handbook specifies a particular TC position (e.g., “use TC at coldest point / largest thermal mass / center pad”), follow that. If it describes a rule (e.g., “use the coldest thermocouple”), implement the rule exactly as defined.
4. If a run has **no thermocouple data**, it is **failing** for peak-temperature compliance (Q03 requirement).

---

## 1) Load & normalize input data

### 1.1 Load CSVs
Use pandas; keep raw columns intact initially.

- `thermocouples.csv`: must contain at least `run_id`, `tc_id`, time column, temperature column (names may vary).
- `mes_log.csv`: typically holds run settings (conveyor speed, recipe, board_family, etc.).
- `test_defects.csv`: defect counts per run/board (for Q05 quality ranking).

### 1.2 Standardize time base (critical)
For each `(run_id, tc_id)` series:

- Sort by timestamp.
- Convert time to seconds (float). If timestamps are datetimes, compute `t_s = (t - t0).total_seconds()`.
- Drop duplicate timestamps (keep last) to avoid division-by-zero.

### 1.3 Standardize temperature
Ensure temperature is numeric in °C.

### 1.4 Guardrails
If any required column is missing, do not invent it—emit `null` fields and mark runs as non-compliant where required.

---

## 2) Extract process definitions & limits from `handbook.pdf`

### 2.1 Extract text
Use `pdfplumber` (or similar) to read all pages and join text.

### 2.2 Find these handbook items (must be explicit)
You must locate and parse exact values from the handbook (via regex + context checks):

**Q01 (Preheat ramp):**
- Definition of **preheat stage**
- Applicable **temperature region** for ramp calculation (e.g., from `T_preheat_start` to `T_preheat_end`, or “from ambient to soak”, etc.)
- The **ramp rate equation** (confirm from handbook)
- The **allowable maximum ramp rate limit** (°C/s)

**Q02 (TAL):**
- Definition of **Time Above Liquidus (TAL)**
- The **liquidus temperature** to use (°C) (and whether it is fixed, alloy-dependent, or sourced from MES)
- TAL measurement window definition (this can differ by handbook)
- Required **min TAL** and **max TAL** thresholds (seconds)

**Q03 (Peak):**
- Minimum required peak temperature (°C) and any additional constraints if specified

**Q04 (Conveyor feasibility):**
- Board geometry inputs (where they come from: MES fields, recipe tables, etc.)
- Thermal dwell requirement definition
- Allowable conveyor speed rule/range and the equation relating speed to dwell

If multiple sections conflict, prefer:
1) explicit “Process Window / Specification” tables,
2) “Quality Requirements” sections,
3) general descriptive text.

If multiple values exist for different alloys/recipes, select the one that matches the dataset context (look for alloy name in MES logs/recipe name in mes_log). Otherwise keep values `null`.

---

## 3) Representative thermocouple selection (must follow handbook)

The tasks may require outputting one tc_id per run. The handbook may instead require “all points must meet spec” or specify a particular TC location.

### 3.1 Implement handbook rule literally
Search the handbook for phrases like:
- “representative thermocouple”
- “use the coldest thermocouple”
- “largest thermal mass / worst-case location”
- “acceptance based on minimum peak across all thermocouples”
- a named placement (e.g., “center pad”, “BGA”, “connector”) that maps to a tc_id convention

Then implement exactly.

### 3.2 Deterministic fallback if the handbook does NOT define a single representative TC
Do **not** introduce extra tie-break criteria that the handbook did not state.

Use a conservative, compliance-driven rule:
- If the spec effectively applies to **all** monitored points (common), compute compliance per TC.
  - If **any** TC is non-compliant, select the TC that is *most non-compliant* (largest violation magnitude); tie-break by smallest `tc_id`.
  - If **all** TCs are compliant, select the TC with the *smallest margin* to the nearest limit; tie-break by smallest `tc_id`.

For two-sided window specs (e.g., TAL with min and max):
- violation magnitude = `max(min_req - value, value - max_req, 0)`
- compliant margin = `min(value - min_req, max_req - value)`

If the metric is uncomputable (`null`) for a TC, treat it as non-compliant for selection purposes (cannot demonstrate compliance), and deterministically pick smallest `tc_id` among the nulls.

### 3.3 Output requirement mapping
- **Q01**: output one tc_id per run in `max_ramp_by_run[run_id]`.
- **Q02**: output one row per run with representative `tc_id` and TAL.
- **Q03**: output one tc_id per run with `peak_temp_c` (often the minimum peak across TCs when “all points must meet minimum peak”).

---

## 4) Q01 — Max preheat ramp rate per run

### 4.1 Determine preheat region from handbook
From handbook, obtain either:
- a temperature band `[T_low, T_high]` that defines preheat for ramp calculation, or
- a time/zone definition that can be translated to temperature bounds.

If only a zone-based definition exists but no zone timestamps exist in data, you cannot compute; emit `null`.

### 4.2 Ramp equation
Use the handbook’s equation. If it states standard slope:

- For consecutive points `i -> i+1` in the preheat window:
  - `ramp_i = (T[i+1] - T[i]) / (t[i+1] - t[i])`

Then:
- Consider only segments fully within the preheat temperature region (or use a crossing-aware approach if the handbook specifies it).
- Compute `max_preheat_ramp = max(ramp_i)`.

### 4.3 Representative TC for Q01
Select representative TC per handbook. If handbook indicates “worst-case vs limit”, select the TC with the **maximum** `max_preheat_ramp` (tie by smallest tc_id).

### 4.4 Violations
- `ramp_rate_limit_c_per_s`: the handbook limit.
- A run violates if representative `max_preheat_ramp_c_per_s > limit`.
- If limit is known but ramp cannot be computed, set ramp to `null` and include run in `violating_runs` (cannot demonstrate compliance).

---

## 5) Q02 — Time Above Liquidus (TAL) per run

### 5.1 Identify liquidus and TAL thresholds
From handbook extract:
- `T_liquidus_c`
- required min/max TAL (seconds)
- TAL measurement window definition

### 5.2 Compute TAL strictly following the handbook’s TAL definition
Handbooks commonly define TAL in one of two ways—use the one that matches the handbook wording:

A) **Total time above liquidus** (recommended when handbook says “time above liquidus” without further qualifiers)
- Compute TAL by summing time above `T_liquidus_c` across the profile using linear interpolation at crossings.

B) **Span from first up-crossing to last down-crossing**
- If the handbook explicitly defines TAL as “from first crossing above liquidus (rising) to last crossing below liquidus (cooling)”, compute:
  - `tal_s = t_down_last - t_up_first`
  - using linear interpolation to find crossing times.

If the profile never exceeds liquidus:
- If the handbook definition is “total time above”, TAL is `0`.
- If the handbook uses a span definition but does not specify behavior when never reaching liquidus, set `tal_s = null` (cannot satisfy the definition) and mark non-compliant.

### 5.3 Representative TC for Q02 (location hint)
This must follow the handbook.

- If the handbook specifies a TC location, pick that tc_id.
- If the handbook requires **all points** to meet TAL limits, compute TAL per TC and apply the fallback in §3.2:
  - if any TC violates min/max TAL, select the most-violating TC (window violation magnitude: `max(min_req - tal, tal - max_req, 0)`);
  - else select the smallest-margin TC (margin: `min(tal - min_req, max_req - tal)`).

Avoid adding extra tie-break rules (e.g., “then tie-break by minimum peak”) unless the handbook explicitly instructs that.

### 5.4 Compliance status
For the representative TC per run:
- compliant if `required_min_tal_s <= tal_s <= required_max_tal_s`.
- if `tal_s` is `null`, status is `non-compliant`.

---

## 6) Q03 — Peak temperature requirement per run

### 6.1 Extract peak requirement
From handbook get `required_min_peak_c` (and any max if present; only min is required by the prompt output).

### 6.2 Compute peak per TC
For each `(run_id, tc_id)`:
- `peak_temp = max(T)`.

### 6.3 Representative TC for Q03
If requirement is “all monitored points must reach minimum peak”, then per run select the TC with **minimum peak** (worst-case), tie-break by smallest tc_id.

### 6.4 Missing data rule
If a run has no thermocouple data:
- It is failing.
- Output `tc_id: null`, `peak_temp_c: null`, still include run in `min_peak_by_run`.

---

## 7) Q04 — Conveyor speed feasibility

### 7.1 Extract constraints from handbook
Find:
- allowable conveyor speed range and/or
- dwell/time-in-oven requirements and how to compute dwell based on heated length / zone length / board geometry.

Identify where **board geometry** comes from (MES fields, recipe, etc.). If the handbook says board length/width matters, pull those fields from MES log.

### 7.2 Compute required minimum speed
Only compute if handbook provides a computable formula that yields a true minimum speed.

If required parameters are missing, set `required_min_speed_cm_min = null` and `meets = false`.

### 7.3 Actual speed
Obtain actual speed per run from `mes_log.csv` (preferred) or other explicit run settings. Do not infer from thermocouple duration unless the handbook explicitly allows that.

---

## 8) Q05 — Best run per board_family (quality + efficiency)

### 8.1 Join datasets
- Determine `board_family` per run from MES logs.
- Determine quality metrics from `test_defects.csv` (e.g., total defects, defect rate). Use only columns present.
- Determine efficiency metric from MES (e.g., conveyor speed, cycle time). Use only columns present.

### 8.2 Eligibility filter
Prefer runs that are compliant across Q01–Q04.

If compliance cannot be computed due to missing handbook parameters, treat that check as unknown; do not claim compliance.

### 8.3 Select best + runner-ups per family
For each `board_family`:
- pick best run_id by ranking:
  1) no known violations,
  2) lower defects,
  3) higher throughput within feasibility.
- `runner_up_run_ids`: all other run_ids in that family sorted ascending.

---

## 9) Formatting & file-writing checklist (completion conditions)

- All outputs written to `/app/output/` with exact filenames.
- Round floats to **2 decimals** at serialization time.
- Sort:
  - run_id arrays ascending
  - Q02/Q04/Q05 arrays sorted as required
- Use `null` when a value is not computable from available data/handbook.
- Never embed handbook text in the output JSON unless explicitly asked.
