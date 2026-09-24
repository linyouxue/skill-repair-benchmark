---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when a task requires answering multi-part manufacturing/process-engineering questions grounded in a domain **handbook (PDF)** plus supporting **structured data files** (e.g., CSV logs, sensor traces, defect tables), and requires writing JSON answer files to a specific output directory in a strict schema.

Target-contract essentials (at a high level):
- All thresholds, definitions, equations, temperature regions, time windows, geometry, dwell requirements, and selection rules must come from the handbook — never guessed or assumed from prior knowledge.
- Numeric answers must be computed from the provided data files (sensor, MES, defects), not fabricated.
- Each sub-question produces its own JSON file with a strictly specified schema, float rounding, sort order, and `null` policy.
- "Best per group" or ranking questions require you to combine handbook-defined quality/compliance criteria with efficiency signals from the data.

Evidence to gather before acting:
1. Extract handbook text (PDF → text) and search for the exact section names referenced in each question (e.g., preheat definition, ramp equation, liquidus, TAL window, peak temperature spec, conveyor/dwell rules, tie-breakers, thermocouple selection rule).
2. Inspect every CSV: columns, units, run_id keys, timestamps or time axis, thermocouple ids, any join keys (run_id ↔ board_family ↔ board_id).
3. Verify units before computing (°C vs K, s vs ms, cm/min vs mm/s, sample rate for ramp = dT/dt).
4. Identify the handbook's rule for choosing a "representative" thermocouple when several are present (e.g., component vs board, hottest, coldest, specific channel).

## Possible Failure Modes
- Hard-coding thresholds (ramp limit, liquidus temperature, min/max TAL, min peak, conveyor speed bounds, board dimensions) from memory instead of extracting them from the handbook.
- Using the wrong temperature window for "preheat" — computing ramp across the whole profile rather than only the handbook-defined preheat region.
- Computing ramp rate as (Tmax − Tmin)/Δt over the region instead of the handbook's specified equation (often a sliding/instantaneous dT/dt, sometimes over a fixed window).
- Selecting the wrong thermocouple per run (e.g., averaging all TCs, or picking max, when the handbook prescribes a specific rule — often "worst-case" or a named channel).
- TAL computation errors: not interpolating crossings of the liquidus line, double-counting multiple excursions incorrectly, or ignoring runs with no data (should be flagged, not silently skipped).
- Peak temperature: treating missing thermocouple data as "pass" or as null instead of the required "failing" per the contract.
- Conveyor feasibility: mixing units (cm vs mm, min vs s), or ignoring that required dwell time comes from summing handbook zone requirements, then converting via board length.
- "Best run" selection: inventing a scoring formula rather than following handbook's stated quality/efficiency priorities and tie-breakers; forgetting that non-compliant runs are typically ineligible.
- Output schema drift: missing keys, wrong nesting, unsorted arrays, unrounded floats, using `"None"` string instead of JSON `null`, or omitting `runner_up_run_ids` when empty.
- Writing outputs to the wrong directory or filename; not creating `/app/output/`.
- Copying values, ids, or structural conventions from unrelated retrieved examples — the retrieved examples here are generic Python coding tasks and contribute no domain facts.

## Possible procedures
1. **Ingest the handbook once, cache the facts.** Use a PDF text extractor; grep for keywords per question (preheat, ramp, liquidus, TAL, peak, conveyor, dwell, zone, board, tie-breaker). Record each numeric threshold with its unit and section reference in a small dict you reuse across questions.
2. **Load CSVs with pandas.** Confirm dtypes and time column. Group thermocouple data by `run_id` and `tc_id`. Confirm every run in MES has (or does not have) thermocouple coverage — this drives null/failing logic.
3. **Per-run temperature analysis pipeline:**
   - Slice the profile to the handbook-defined region (preheat / above-liquidus / peak).
   - Apply the handbook's exact equation (e.g., ramp = ΔT/Δt on consecutive samples; TAL = time where T ≥ liquidus, interpolated at boundary crossings).
   - Apply the handbook's TC-selection rule to pick the representative `tc_id`.
4. **Compliance decisions** must reference handbook thresholds only; do not invent tolerance. Encode limits as named constants sourced from the handbook.
5. **Conveyor feasibility:** required_min (or max) speed = board_length / required_total_dwell (watch units). Compare to actual speed from MES.
6. **Best-per-family selection:** first filter to compliant runs across all prior checks; then rank by the handbook's stated primary metric (often defect rate or yield from `test_defects.csv`), break ties by efficiency (speed/throughput). Every other run in the family (compliant or not, unless spec says otherwise) goes into `runner_up_run_ids`, sorted ascending.
7. **Write JSON:** build dicts matching the exact schema shown in the prompt; round floats with `round(x, 2)`; sort lists by the specified key; ensure `null` where data is absent; `os.makedirs('/app/output', exist_ok=True)` before writing.
8. **Recovery checks:**
   - If a handbook value cannot be located, re-search with alternative keywords/synonyms before defaulting; do not guess.
   - If a run has zero thermocouple rows, follow the contract's "no data ⇒ failing" rule and still emit the run in output with appropriate nulls/False.
   - Sanity-check ramp signs, TAL non-negativity, and that peak ≥ liquidus for any compliant run.

## Verification Checklist
- [ ] Every threshold, equation, region, window, and selection rule used is quoted/traceable to the handbook (not assumed).
- [ ] All five output files exist at `/app/output/q0{1..5}.json` with the exact top-level structure specified in the prompt.
- [ ] Floats rounded to 2 decimals; arrays sorted ascending by `run_id` / `board_family` / `board_id` as specified.
- [ ] Missing data uses JSON `null`, not strings; booleans are real `true`/`false`.
- [ ] Runs without thermocouple data are handled per the contract (e.g., failing for peak check) and still appear in outputs.
- [ ] Units verified (°C/s for ramps, seconds for TAL, cm/min for conveyor); no unit-mixing.
- [ ] Representative thermocouple per run chosen by handbook rule, not by ad-hoc heuristic.
- [ ] Best-run selection filters by compliance first, then applies handbook's ranking + tie-break; `runner_up_run_ids` present (possibly empty list) and sorted.
- [ ] No values, ids, or schema fragments copied from retrieved examples — they are unrelated.
- [ ] JSON files parse (`json.load` round-trip) and contain every required key even when values are null/empty.
- [ ] Unrelated files under `/app/data/` are not modified; only `/app/output/` is written.
- [ ] If any handbook fact was unresolved, re-check the PDF before falling back — never fabricate a limit.
