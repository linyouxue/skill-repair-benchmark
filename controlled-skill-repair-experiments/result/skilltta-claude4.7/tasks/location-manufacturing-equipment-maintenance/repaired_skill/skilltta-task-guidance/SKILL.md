---
name: skilltta-task-guidance
---

# Reflow Profile Compliance Toolkit — Task Guidance

This skill guides answering reflow-oven profile compliance questions for an automation engineer. All thresholds, equations, and definitions MUST be read from `/app/data/handbook.pdf`. Do not guess numeric limits.

## Inputs (all under `/app/data/`)
- `handbook.pdf` — authoritative source for definitions, equations, limits, geometry, and representative-TC rules.
- `mes_log.csv` — per-run metadata (run_id, board_family/board_id, conveyor speed, solder alloy, etc.).
- `thermocouples.csv` — time-series temperature samples (run_id, tc_id, time_s, temp_c).
- `test_defects.csv` — per-run defect counts / yields.
- Output directory: `/app/output/` — write `q01.json` … `q05.json`.

## General workflow
1. **Read the handbook first.** Extract and record in-memory:
   - Preheat temperature region (start_c, end_c) and ramp equation (typically `dT/dt` sample-to-sample or over the region).
   - Preheat max ramp rate limit (°C/s).
   - Solder liquidus temperature per alloy (e.g., SAC305 ≈ 217°C, Sn63Pb37 ≈ 183°C — but USE handbook values).
   - TAL min/max window (seconds).
   - Required minimum peak temperature per alloy/board_family.
   - Board geometry (length cm) and minimum thermal dwell time → min conveyor speed formula, plus machine conveyor speed limits.
   - Representative-TC selection rule (e.g., "worst-case TC": the TC with the maximum ramp for Q1, the TC with the **minimum TAL / minimum peak** for Q2/Q3, etc.).
2. **Join** MES metadata with thermocouple series by `run_id`. Determine solder alloy / board_family per run to look up alloy-specific thresholds.
3. **Per run, per TC**, compute metrics on sorted time series. Then select the representative TC per the handbook rule.
4. **Write JSON** with required schema; round floats to 2 decimals; sort arrays by `run_id` (or `board_family` for Q5); use `null` where data missing.
5. **Runs with no TC data**: for Q1/Q2 use `null`; for Q3 they are automatically failing (per prompt).

## Representative thermocouple selection (critical)
The handbook specifies worst-case TC selection. Apply per-metric:
- **Q1 (max preheat ramp)**: TC with the **highest** max-ramp in the preheat window (worst offender).
- **Q2 (TAL)**: Follow handbook — typically the TC with the **shortest TAL** (worst-case for min-TAL compliance). If handbook specifies otherwise (e.g., leading-edge or center TC), honor that. Record `tc_id` of that representative TC and compare its `tal_s` against required_min/max.
- **Q3 (peak)**: TC with the **lowest** peak temperature (worst-case against min-peak requirement).

## Q1 — Max preheat ramp
- Preheat window: handbook's temperature band (e.g., 50→150°C). For each TC, filter samples where temp lies in the band (or interpolate crossings if handbook requires).
- Compute instantaneous ramp `(T[i+1]-T[i])/(t[i+1]-t[i])`. Take the max.
- Compare each run's representative TC max against `ramp_rate_limit_c_per_s`. Violating if > limit.

## Q2 — TAL
- For each TC, find contiguous time where `temp >= liquidus(alloy)`. Sum durations (handle multiple crossings via linear interpolation at crossings for accuracy).
- Select representative TC per handbook (worst-case for min TAL).
- `status = compliant` iff `required_min_tal_s <= tal_s <= required_max_tal_s`.

## Q3 — Peak temperature
- Per run: representative TC = TC with lowest peak. Compare against `required_min_peak_c` from handbook for that alloy/family. Failing if peak < required or no TC data.

## Q4 — Conveyor speed feasibility
- From handbook: `required_min_speed = board_length / max_dwell` and `required_max_speed = board_length / min_dwell` (or whichever direction the handbook defines; typically min speed derived from max allowed total dwell, max speed from min thermal dwell). Follow the exact handbook formula.
- Compare `actual_speed_cm_min` from MES; `meets = true` iff within handbook's allowable range.
- Output only `required_min_speed_cm_min` as per schema; still ensure actual satisfies all handbook constraints before `meets=true`.

## Q5 — Best run per board_family
- Quality signal: lower defects (from `test_defects.csv`), compliance across Q1–Q4 (prefer runs passing all).
- Efficiency signal: higher throughput (higher conveyor speed) among compliant runs, or lower cycle time.
- Ranking rule: (1) all-compliant first; (2) fewest defects; (3) highest conveyor speed as tiebreak.
- For each board_family, pick top as `best_run_id`; list the rest in `runner_up_run_ids` sorted ascending.

## Output discipline
- Create `/app/output/` if missing. Write exactly: `q01.json`, `q02.json`, `q03.json`, `q04.json`, `q05.json`.
- Match schemas verbatim (keys, nesting, types). Round floats to 2 decimals using Python `round(x, 2)`.
- Sort arrays ascending by `run_id` (Q2, Q4) or `board_family` (Q5). For dict-of-runs (Q1, Q3), insert keys in ascending `run_id` order.
- Use `null` for missing numeric fields; use empty list `[]` for empty arrays.
- **Task is complete only when all five JSON files exist, parse as valid JSON, and conform to the schemas above.**

## Patterns borrowed from retrieved examples
- Deterministic, side-effect-free data processing with explicit input validation (TypeError-style guards) — validate CSV columns exist before computing.
- CSV iteration with `csv`/`pandas`; counter/aggregation patterns (`Counter`) for ranking defects.
- JSON serialization with `json.dump(..., indent=2)` and explicit key ordering.
