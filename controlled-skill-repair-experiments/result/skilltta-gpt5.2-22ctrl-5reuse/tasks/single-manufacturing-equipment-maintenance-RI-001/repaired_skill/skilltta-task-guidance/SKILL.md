---
name: skilltta-task-guidance
---

# SkillTTA Temporary Task Guidance: Reflow Profile Compliance (Handbook + CSV Logs)

## Goal
Produce five machine-readable deliverables (`/app/output/q01.json` … `q05.json`) by:
1) extracting *all required definitions, equations, and limits* from `handbook.pdf`,
2) computing metrics from `thermocouples.csv` (and supporting files),
3) determining compliance without guessing (use `null` when necessary),
4) writing JSON in the exact requested schema, with correct rounding and sorting.

This skill is optimized for “do not hallucinate” tasks: any numeric requirement **must** be traceable to the handbook text.

---

## Files & Expected Use
- `/app/data/handbook.pdf` — authoritative source for:
  - definition of **preheat** and its temperature window,
  - **ramp rate equation** and **allowable ramp limit** (and whether ramp is ramp-up only vs absolute),
  - **TAL** definition, **liquidus temperature**, TAL measurement window/bounds, min/max TAL,
  - **peak temperature** requirements,
  - **conveyor speed** feasibility constraints (board geometry, dwell/time-in-oven requirements, allowable min/max speed),
  - how to select the **representative thermocouple** (e.g., “coldest point TC”, “heaviest component TC”).
- `/app/data/thermocouples.csv` — time-series temperature data per run and thermocouple.
- `/app/data/mes_log.csv` — typically contains setpoints, speed, recipe, board_family mapping.
- `/app/data/test_defects.csv` — defect counts/rates to pick “best run per board_family”.

---

## Non-negotiable Output Rules
- **No guessing.** If a value cannot be derived from the handbook or computed from data, output `null`.
- Round floats to **2 decimals**.
- Sort:
  - arrays by `run_id` ascending,
  - dictionaries keyed by run_id: write keys in ascending order when emitting JSON.
- Q02 array must be **one record per run_id** (representative TC per run).
- Q04 array must be **one record per run_id**.
- If a run has **no thermocouple data**, it **fails** peak temp requirement (per task).

---

## Step 0 — Load Data Robustly (Type/Column Validation)
Follow the “validate early” pattern:
- Assert the input files exist.
- Read CSVs with pandas; normalize column names (strip, lower).
- Verify required columns are present before computing.

Recommended checks:
- `thermocouples.csv` must contain at least: `run_id`, `tc_id`, `time_s` (or timestamp), `temp_c`.
- `mes_log.csv` must contain `run_id` and a conveyor speed field (units must be confirmed).
- `test_defects.csv` must contain `run_id` and defect metric(s).

If time is a timestamp string, convert to seconds relative to run start:
- group by `(run_id, tc_id)`
- sort by time
- subtract first timestamp.

Define the run universe deterministically:
- Prefer run_ids from `mes_log.csv`.
- If missing, fall back to run_ids from `thermocouples.csv`.

---

## Step 1 — Extract Handbook Requirements (PDF → Structured Requirements)
### 1.1 Parse handbook.pdf
Use a PDF text extraction tool (e.g., `pdfplumber` or `PyMuPDF`). Build helper utilities:
- `extract_text_all_pages()`
- `find_snippets(keywords: list[str]) -> list[(page, snippet)]`

### 1.2 Required handbook fields to extract (must be literal)
Create a `requirements` dict with these keys populated from handbook text:

**Preheat / Ramp:**
- `preheat_definition_text`
- `preheat_temp_window`: e.g., `{ "start_c": X, "end_c": Y }` OR `{ "between_c": [X, Y] }`
- `ramp_equation_text` (e.g., “(T2−T1)/(t2−t1)”)
- `max_ramp_limit_c_per_s`
- whether ramp limit applies to ramp-up only or absolute slope magnitude.

**TAL:**
- `liquidus_temp_c` (solder liquidus)
- `tal_definition_text`
- `tal_window_definition_text` (if handbook defines boundaries beyond “above liquidus”)
- `required_min_tal_s`, `required_max_tal_s`
- inequality: at/above vs above.

**Peak:**
- `required_min_peak_c` (and `required_max_peak_c` if handbook defines it)
- Clarify whether peak is per-TC, and whether to use coldest/hottest TC.

**Conveyor speed feasibility:**
- allowable speed bounds OR calculation based on:
  - board geometry (length in travel direction),
  - required dwell time / time-in-oven,
  - oven heated length / zone lengths,
  - any stated min/max conveyor speed.

**Representative thermocouple selection:**
- Extract the rule (e.g., “Use TC at coldest solder joint” or “TC on largest thermal mass component”).

### 1.3 If multiple values appear
Use a consistent selection procedure:
- Prefer values in sections titled “Process Window”, “Profile Requirements”, “Acceptance Criteria”.
- If multiple solder alloys are listed, pick the one explicitly associated with the product/runs (often in MES log/recipe); if not determinable, set requirement to `null` and mark compliance as non-compliant where required.

Store page references internally (not required in JSON), to ensure traceability during debugging.

---

## Step 2 — Thermocouple Preprocessing
For each `(run_id, tc_id)`:
1) sort by time,
2) remove duplicate time points if present,
3) ensure temperature is numeric,
4) compute point-to-point slopes:
   - `ramp_i = (temp[i]-temp[i-1]) / (time[i]-time[i-1])`
   - ignore intervals where `Δt <= 0`.

---

## Q1 — Maximum Temperature Ramp Rate During Preheat (per run)
### 3.1 Determine the “preheat region”
Use handbook’s definition:
- If it defines preheat as a temperature range, only consider segments where both endpoints fall in that range (unless handbook says otherwise).
- If it defines preheat by zones or time, map it as instructed.

If the handbook is ambiguous and cannot be mapped reproducibly, output `null` ramp and do not invent a mapping.

### 3.2 Ramp calculation
Use handbook’s ramp equation. Determine from handbook whether:
- ramp limit applies to ramp-up only (use maximum positive slope), or
- ramp is absolute slope (use maximum absolute value).

### 3.3 Representative thermocouple selection
Follow handbook rule **first**.
Fallback only if handbook does not specify:
- For ramp-rate compliance, pick the **maximum** preheat ramp across thermocouples (most conservative vs an upper limit).

### 3.4 Output for Q1
- `ramp_rate_limit_c_per_s`: from handbook.
- `max_ramp_by_run[run_id] = { tc_id, max_preheat_ramp_c_per_s }`.
- `violating_runs`: runs where `max_preheat_ramp > limit`.

If a run has no valid ramp segments in preheat, set `max_preheat_ramp_c_per_s: null`.

---

## Q2 — Time Above Liquidus (TAL) per run (one row per run)
### 4.1 Liquidus temperature
Extract `liquidus_temp_c` from handbook.

### 4.2 TAL computation
Compute time above liquidus using linear interpolation at crossings.
Use handbook inequality:
- “at or above” → `>=` (inclusive)
- “above” → `>` (strict)
- if not explicit → default to inclusive.

If the handbook defines a TAL measurement window (e.g., certain zones or time boundaries) beyond “above liquidus”, apply that window deterministically; otherwise compute TAL on the full curve.

### 4.3 Representative thermocouple for TAL
Follow handbook. If unspecified, choose conservative:
- Use **windowed-critical** selection (prefer largest violation if any; else smallest margin to boundary).

### 4.4 Compliance thresholds
Extract required min/max TAL (seconds) from handbook:
- `required_min_tal_s`, `required_max_tal_s`.

Status:
- `compliant` if `min <= TAL <= max`.
- `non-compliant` if outside bounds or if TAL cannot be computed (`null`).

### 4.5 Output for Q2
Emit an array of objects sorted by `run_id` with **exactly one row per run_id**.

---

## Q3 — Peak Temperature Requirement (per run)
### 5.1 Compute peak per thermocouple
For each `(run_id, tc_id)`:
- `peak_temp = max(temp_c)`.

### 5.2 Select thermocouple for acceptance
Follow handbook.
Fallback if unspecified:
- For a minimum peak requirement, use the **minimum peak** across thermocouples (coldest point).

### 5.3 Missing data rule
Per task: if a run has **no thermocouple data**, it is failing.

### 5.4 Output for Q3
- `min_peak_by_run[run_id] = { tc_id, peak_temp_c, required_min_peak_c }` where `tc_id` is the selected “most critical” TC.
- `failing_runs`: those with missing TC data or peak constraint violations.

If handbook defines a max peak too, enforce it for failing/non-failing, even though the schema does not include `required_max_peak_c`.

---

## Q4 — Conveyor Speed Feasibility (per run; one row per run)
### 6.1 Identify required information
From handbook, extract one of these:
- explicit allowable conveyor speed range (min/max), OR
- a computation based on heated length / required dwell time or max time-in-oven.

### 6.2 Compute required minimum speed
Only compute if the handbook provides a deterministic formula.

### 6.3 Actual speed
Obtain actual conveyor speed from `mes_log.csv` for each `run_id`.
Confirm units:
- Convert only when units are explicit.
- If units cannot be determined, set `actual_speed_cm_min = null`.

### 6.4 Meets
`meets` must reflect all applicable constraints.
If any needed value is `null`, set `meets = false`.

### 6.5 Output
Array sorted by `run_id` with **exactly one object per run_id**.

---

## Q5 — Best Run per board_family (quality + efficiency)
### 7.1 Join needed fields
Create a per-run table from:
- MES: `run_id -> board_family`, plus throughput proxies (e.g., conveyor speed) if available.
- Defects: `run_id -> defect_count`, `defect_rate`, or pass/fail.
- Compliance results from Q1–Q4.

### 7.2 Define “eligible” runs
A run is eligible only if it meets process compliance (Q1–Q4) and required metrics are not null.

### 7.3 Ranking strategy (do not invent weights)
- Primary: lowest defects (quality).
- Secondary: highest throughput proxy available (e.g., conveyor speed) among eligible runs.
- Tie-breaker: `run_id` ascending.

### 7.4 Output
For each `board_family` (sorted ascending):
- `best_run_id`: top-ranked eligible run (or null if none).
- `runner_up_run_ids`: **all other run_ids** for that family (sorted), regardless of eligibility.

---

## Implementation Notes (Reliability)
- Always group computations by run; never mix time axes across runs.
- Use linear interpolation for TAL crossings to avoid discretization bias.
- When writing JSON, ensure native Python types (no numpy types) to avoid serialization errors.

---

## Minimal Checklist Before Finalizing
1) Handbook extraction filled all required limits; otherwise propagate `null` and mark non-compliance where required.
2) Thermocouple computations done per run + TC with sorted times.
3) Representative TC selection follows handbook; fallback is conservative and explicitly documented.
4) Outputs rounded to 2 decimals, sorted, schemas match.
5) Files written:
   - `/app/output/q01.json`
   - `/app/output/q02.json`
   - `/app/output/q03.json`
   - `/app/output/q04.json`
   - `/app/output/q05.json`
