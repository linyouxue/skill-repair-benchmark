---
name: skilltta-task-guidance
description: Temporary guidance for reflow profile compliance analysis across 5 sub-questions using handbook.pdf, mes_log.csv, thermocouples.csv, test_defects.csv
---

# Reflow Profile Compliance Toolkit — Task Guidance

## General workflow
1. **Always read the handbook first** (`/app/data/handbook.pdf`) to extract authoritative definitions, thresholds, equations, and windows. Do NOT hardcode numeric limits from memory — parse them from the PDF (use `pdfplumber` or `pypdf`).
2. Load `mes_log.csv` (run metadata: run_id, board_family, board_id, conveyor speed, zone setpoints, etc.), `thermocouples.csv` (time-series temperature per run per tc_id), and `test_defects.csv` (post-reflow defect counts).
3. For every run, group thermocouple data by `(run_id, tc_id)` and sort by time before computing derivatives or windows.
4. Write outputs to `/app/output/qNN.json`, rounding floats to 2 decimals, sorting arrays ascending by key, using `null` where undefined.

## Representative thermocouple selection (CRITICAL)
The handbook specifies how to pick the representative tc per run. Common rule patterns to check:
- **Worst-case / most-conservative** thermocouple (e.g., for ramp: the tc with the HIGHEST max ramp; for peak: the tc with the LOWEST peak; for TAL: the tc with the SHORTEST TAL — because that is the hottest-risk or coolest-risk sensor the handbook flags).
- Re-read the handbook section for EACH question — the representative rule may differ per metric. In particular for **Q02 (TAL)** the representative tc is typically the one with the **minimum TAL** (coolest joint, worst for wetting), not the maximum. Do not reuse Q01's selection rule blindly.
- If handbook says "use the coolest sensor" / "leading indicator" / "corner tc", honor that exact wording.

## Q01 — Max preheat ramp rate
- Extract from handbook: preheat temperature region (e.g., 50 °C → 150 °C or similar), ramp equation (dT/dt via finite difference), limit (°C/s).
- For each (run, tc): filter samples whose temperature lies in the preheat band, compute per-sample `(T[i+1]-T[i])/(t[i+1]-t[i])`, take max.
- Representative tc per run = tc with the **largest** max preheat ramp (worst case).
- `violating_runs` = runs whose representative max ramp > limit.

## Q02 — Time Above Liquidus (TAL)
- Extract liquidus temperature (solder alloy), TAL min and max window from handbook.
- For each (run, tc): compute total seconds where T ≥ liquidus (integrate using trapezoidal crossing or sum of dt where T≥Tliq, interpolating the entry/exit crossings for accuracy).
- Representative tc: per handbook — typically the tc with **minimum TAL** (worst-case joint). Verify by re-reading the TAL section.
- `status` = compliant iff `required_min ≤ tal_s ≤ required_max`.

## Q03 — Peak temperature
- Extract required minimum peak temperature from handbook (and max if specified).
- Per (run, tc): peak = max(T). Representative tc = tc with **lowest** peak (coolest joint).
- If a run has NO thermocouple data → it fails automatically; include it in `failing_runs` with null fields where appropriate.

## Q04 — Conveyor speed feasibility
- Extract from handbook: board length (geometry), heated tunnel length or zone length, required thermal dwell time (sum of preheat+soak+reflow+cooling residence requirements), min/max allowable conveyor speed.
- `required_min_speed_cm_min` is typically derived from max allowable dwell constraint OR handbook-stated minimum; `actual_speed_cm_min` comes from `mes_log.csv`.
- `meets` = actual within handbook speed window AND satisfies dwell requirement for that board_family.

## Q05 — Best run per board_family
- Combine: profile compliance (Q01–Q03 pass), TAL within window, defect rate from `test_defects.csv` (lower = better quality), throughput/efficiency (higher conveyor speed within spec = better).
- Rank: first by compliance (compliant runs beat non-compliant), then by lowest defect rate, then by highest feasible conveyor speed.
- `best_run_id` = top; `runner_up_run_ids` = remaining runs in that family sorted by rank (ascending run_id when tied).

## Patterns borrowed from retrieved examples
- **Deterministic I/O with explicit schema** (BigCodeBench/764 CSV writer): always emit the exact JSON schema requested, in the order/shape specified, even for empty lists — mirrors the discipline of writing CSV with fixed fieldnames.
- **Group-and-aggregate** (BigCodeBench/69 salary histogram per department): the `groupby(run_id, tc_id)` → aggregate pattern is identical. Iterate groups, compute scalar metric, then reduce across tcs per run using the handbook's selection rule.
- **Parse-then-filter-then-count** (BigCodeBench/761 JSON cleanup): mirror this for handbook parsing — extract raw text, regex out the specific numeric thresholds (e.g., `r"([0-9.]+)\s*°?C/s"`, `r"liquidus[^0-9]*([0-9.]+)"`), validate, then apply. Never guess if regex fails — re-read with a different page/section.

## Validation checklist before writing JSON
- [ ] All limits came from handbook text extraction, not assumptions.
- [ ] Representative tc rule applied PER QUESTION (not globally reused).
- [ ] Floats rounded to 2 decimals.
- [ ] Arrays sorted ascending by `run_id` / `board_family` / `board_id`.
- [ ] Runs without thermocouple data handled explicitly (fail for Q03, null fields elsewhere).
- [ ] Output file path exactly `/app/output/qNN.json`.
