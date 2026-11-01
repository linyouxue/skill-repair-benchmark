---
name: skilltta-task-guidance
description: Temporary guidance for the reflow profile compliance toolkit task (Q1–Q5). Focuses on strict handbook-grounded parsing, representative thermocouple selection, and deliverable/completion criteria.
---

# Reflow Profile Compliance Toolkit — Task Guidance

## Inputs
- `/app/data/handbook.pdf` — authoritative source for all thresholds, definitions, equations, windows, geometry, speed limits.
- `/app/data/mes_log.csv` — run metadata: `run_id`, `board_family`, `board_id`, `conveyor_speed_cm_min`, solder alloy, etc.
- `/app/data/thermocouples.csv` — per-run, per-TC time series (`run_id`, `tc_id`, `time_s`, `temp_c`).
- `/app/data/test_defects.csv` — defect counts/rates per run for Q5 quality scoring.

## Hard Rules
1. **Never hallucinate numbers.** Every threshold (ramp limit, liquidus temp, TAL min/max, peak min, board length, dwell seconds, max/min conveyor speed) MUST be extracted verbatim from `handbook.pdf`. If a value is not found, set the field to `null` and record it — do not guess.
2. **Deliverables must exist**: write exactly `/app/output/q01.json`, `/app/output/q02.json`, `/app/output/q03.json`, `/app/output/q04.json`, `/app/output/q05.json`. Each must match the schema in the prompt (field names, nesting, types).
3. **Rounding**: round all float values to 2 decimals using Python `round(x, 2)` AFTER all computation (not during).
4. **Sorting**: sort every list output by `run_id` (or `board_family` / `board_id` when that is the primary key) ascending, lexicographic.
5. **Completion criteria**: a question is considered complete only when (a) its JSON file exists, (b) all required keys are present for every run in `mes_log.csv`, (c) `null` is used for genuinely missing data (e.g., runs with no thermocouple rows in Q3 → mark failing, peak null), and (d) numeric fields obey schema types.

## Representative Thermocouple Selection (critical for Q1, Q2, Q3)
The handbook specifies which TC is the "representative" / "controlling" probe (typically the one on the largest thermal mass, or the coolest TC, or a named location like TC_CENTER / TC_BGA). Apply this rule consistently:

- **Q1 (max preheat ramp)**: for each run, compute the max ramp over the preheat region for EVERY tc_id, then pick the TC per the handbook's representative-TC rule. Report that tc_id and its ramp. Do NOT just take the max across TCs unless the handbook says so.
- **Q2 (TAL)**: compute TAL (time where temp ≥ liquidus) per TC. Per the handbook, the representative TC for TAL compliance is typically the **coolest/longest-ramping probe** (worst case for min TAL) OR the one explicitly named. Re-read the handbook's TAL section — do not reuse Q1's selection blindly. If the handbook says "use the TC with the minimum TAL" (worst case), pick argmin; if it names a specific tc_id, use that one.
- **Q3 (peak)**: per handbook, the representative TC for peak is usually the **coolest TC** (lowest peak = worst case for min-peak compliance). Report the min peak across TCs for that run and compare to the handbook minimum.

Always document the selection rule in a code comment citing the handbook section/page.

## Per-Question Procedure

### Q1 — Preheat ramp rate
1. Extract from handbook: preheat definition (temperature window, e.g., 50 °C → 150 °C), ramp equation (ΔT/Δt sliding or point-to-point), allowable max ramp (°C/s).
2. For each (run_id, tc_id): filter samples whose temp is inside the preheat window, compute instantaneous ramp between consecutive samples: `(T[i+1]-T[i])/(t[i+1]-t[i])`. Take the max.
3. Select representative tc per handbook rule → populate `max_ramp_by_run`.
4. `violating_runs` = sorted list of run_ids where representative max > limit.

### Q2 — Time Above Liquidus
1. Extract: liquidus temp (depends on alloy — SAC305 ~217 °C, Sn63Pb37 ~183 °C; use handbook mapping, not assumptions), min TAL, max TAL.
2. For each run, per representative-TC-for-TAL rule, compute total seconds with temp ≥ liquidus. Use trapezoidal/linear interpolation at crossings for accuracy if sample spacing is coarse; otherwise sum Δt where temp ≥ liquidus.
3. Status = `compliant` iff `min ≤ tal_s ≤ max`.

### Q3 — Peak temperature
1. Extract required minimum peak temperature (may depend on alloy / board_family).
2. For each run with TC data: pick representative TC (coolest-peak), report its peak.
3. Runs with no TC rows → include in `failing_runs`, set `peak_temp_c: null`, `tc_id: null`.

### Q4 — Conveyor speed feasibility
1. Extract: board length (cm, by family), required dwell time in reflow zone (s), zone length, allowable conveyor speed range.
2. required_min_speed_cm_min and required_max from handbook formulae; compare to `actual_speed_cm_min` from mes_log.
3. `meets` = true iff actual within [min, max].

### Q5 — Best run per board_family
1. Score each run by combining: Q1/Q2/Q3/Q4 compliance (hard gate) and defect rate from `test_defects.csv` (quality), plus throughput proxy (conveyor speed) for efficiency.
2. Prefer runs that pass all compliance gates; among those, lowest defect rate wins; tiebreak by higher conveyor speed.
3. Output best + sorted runner_ups per family.

## Transferable Patterns from Retrieved Examples
- **Strict schema & type validation** (like BCB/764 TypeError guards): before writing JSON, assert dict shapes and types to catch silent regressions.
- **Deterministic output ordering** (like BCB CSV writers using fixed fieldnames): always sort keys/arrays before dumping.
- **Null/empty-input handling** (like BCB/761 removing None, BCB/764 empty-name case): explicitly handle runs with no TC data → `null`, not crashes.

## Final Checklist Before Finishing
- [ ] All five q0X.json files written under `/app/output/`.
- [ ] Every run_id in mes_log.csv appears where required.
- [ ] Numeric fields rounded to 2 decimals.
- [ ] Arrays sorted ascending by the specified key.
- [ ] Thresholds in outputs match handbook text exactly (spot-check against PDF).
- [ ] Representative-TC rule applied per question (Q2 rule may differ from Q1/Q3).
