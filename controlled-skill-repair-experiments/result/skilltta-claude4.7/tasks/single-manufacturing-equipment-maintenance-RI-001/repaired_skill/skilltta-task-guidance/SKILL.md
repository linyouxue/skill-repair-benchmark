---
name: skilltta-task-guidance
description: Temporary guidance for the reflow-profile-compliance toolkit task. Covers deliverables, data handling patterns, and completion checks for Q1–Q5.
---

# Reflow Profile Compliance — Task Guidance

## Inputs (read-only)
- `/app/data/handbook.pdf` — authoritative source for all thresholds/definitions. Do NOT guess; extract text and quote exact values.
- `/app/data/mes_log.csv` — per-run metadata (run_id, board_family, board_id, conveyor speed, solder alloy, etc.).
- `/app/data/thermocouples.csv` — time-series temperature per (run_id, tc_id).
- `/app/data/test_defects.csv` — per-run defect counts/yield.

## Deliverables (MUST all exist, exact names)
Write every file even if some values are null:
- `/app/output/q01.json`
- `/app/output/q02.json`
- `/app/output/q03.json`
- `/app/output/q04.json`
- `/app/output/q05.json`

Completion is only satisfied when all 5 files are present, valid JSON, follow the exact schema in the prompt, floats rounded to 2 decimals, and arrays sorted ascending by `run_id` / `board_family` / `board_id` as specified.

## General Rules
1. Always derive thresholds (preheat region, ramp limit, liquidus temp per alloy, TAL min/max, peak min, board length, min dwell, allowable conveyor speed) from the handbook. If not found, re-extract PDF (use `pdfplumber` or `pypdf`) rather than guessing.
2. For each run, pick the single most representative thermocouple as defined by the handbook (e.g., center/component TC, or the TC yielding the worst-case per handbook rule). Record `tc_id` used.
3. If a run has no thermocouple samples → treat metrics as null and mark as failing/non-compliant where the question requires.
4. Round all floats with `round(x, 2)` just before serialization. Use `null` (JSON) for missing values, not NaN.
5. Sort output arrays ascending by the key named in the schema.

## Q1 — Max preheat ramp rate
- Preheat region = handbook-defined temperature band (e.g., Tstart→Tend °C).
- Ramp = ΔT/Δt between consecutive samples within that band, per TC.
- Per run, choose representative TC per handbook; report its max ramp.
- A run violates if max_ramp > handbook ramp limit.
- Output includes `ramp_rate_limit_c_per_s`, sorted `violating_runs`, and `max_ramp_by_run` dict keyed by run_id (sorted).

## Q2 — Time Above Liquidus
- Liquidus temperature depends on solder alloy (from MES log) and handbook table (e.g., SAC305 ≈ 217 °C, Sn63Pb37 ≈ 183 °C — confirm from handbook, do not assume).
- TAL = total seconds the representative TC is strictly above liquidus.
- Compare to handbook `required_min_tal_s` and `required_max_tal_s` window.
- Status: `compliant` iff min ≤ tal ≤ max; else `non-compliant`.

## Q3 — Peak temperature
- Required min peak from handbook (often alloy-specific, e.g., liquidus + ΔT).
- Among TCs for a run, choose TC with the MINIMUM peak (worst-case) → that is `min_peak_by_run[run]`.
- Failing if min peak < required or run has no TC data.

## Q4 — Conveyor speed feasibility
- From handbook get: board/zone length L (cm), min total dwell/thermal profile time t_min (s or min), allowable speed range.
- required_min_speed is not the minimum — it is the maximum speed that still gives the required dwell: `v_max_allowed = L / t_min` (convert units to cm/min). Follow the handbook’s exact formula; the field is literally `required_min_speed_cm_min` as named in the schema — populate it with the handbook-derived threshold the actual speed must satisfy.
- `meets = actual_speed_cm_min <= required_min_speed_cm_min` (or whatever direction the handbook defines). Verify direction from handbook text.

## Q5 — Best run per board_family
- Quality signal: lower defect rate / higher yield from `test_defects.csv`.
- Efficiency signal: higher throughput (conveyor speed) or shorter cycle, per handbook guidance; and compliance with Q1–Q4.
- Rank runs within each `board_family`: filter to compliant runs first, then sort by (defect_rate asc, speed desc) or handbook-defined tiebreak.
- `best_run_id` = top; `runner_up_run_ids` = remaining run_ids in that family sorted ascending.

## Patterns Borrowed From Prior Examples
- CSV writing/encoding safety (BigCodeBench/764 style): open with explicit encoding; write deterministically.
- Dict → JSON serialization with Counter/aggregation (BigCodeBench/761 style): build intermediate dicts, then `json.dump(obj, f, indent=2)`.
- Simple numeric aggregation over groups (BigCodeBench/69 style): use `groupby` on run_id/tc_id for ramp and TAL calculations.

## Minimal Pipeline
```
load handbook text -> parse thresholds
load mes_log, thermocouples, test_defects (pandas)
for each run_id:
    for each tc_id: compute preheat ramp max, peak, TAL
    pick representative TC per handbook rules
build q01..q05 dicts
round floats, sort, write JSON to /app/output/
assert all 5 files exist and parse
```

## Final Self-Check Before Finishing
- [ ] All 5 JSON files written to `/app/output/`.
- [ ] Schemas match exactly (keys, nesting, types).
- [ ] Floats rounded to 2 decimals; `null` where data missing.
- [ ] Arrays sorted ascending by specified key.
- [ ] Every threshold used is traceable to a handbook passage, not guessed.
