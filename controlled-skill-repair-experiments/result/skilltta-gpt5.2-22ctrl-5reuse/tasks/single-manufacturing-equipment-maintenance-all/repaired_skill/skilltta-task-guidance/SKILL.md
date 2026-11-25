---
name: skilltta-task-guidance
---

# Reflow Profile Compliance Toolkit — Task Guidance (Temporary Skill)

This skill provides a deterministic, non-hallucinating workflow to answer Q01–Q05 using:
- `/app/data/handbook.pdf`
- `/app/data/thermocouples.csv`
- `/app/data/mes_log.csv`
- `/app/data/test_defects.csv`

It focuses on (1) extracting exact definitions/limits from the handbook, (2) computing metrics from thermocouple/MES data with correct windowing + interpolation, (3) selecting the representative thermocouple per handbook, and (4) writing strictly formatted JSON outputs.

## 0) Global rules (apply to all questions)

### 0.1 No guessing / no hallucination
- **Every numeric threshold (limits, windows, liquidus, peak requirements, conveyor constraints)** must be **directly extracted** from `handbook.pdf`.
- If a required handbook value cannot be found with high confidence:
  - set that value to `null` in output,
  - compute what you can from the raw data,
  - mark compliance conservatively when a binary status is required (see each question’s rules).

### 0.2 Deterministic formatting
- Round all float outputs to **2 decimals**.
- Sort:
  - dict keys by `run_id` ascending,
  - arrays by `run_id` / `board_family` / `board_id` ascending.
- Use JSON `null` for missing values.
- Ensure output directory exists: `/app/output/`.

### 0.3 Data loading expectations
Use `pandas` (or equivalent) and normalize types early.
- `run_id`: string
- `tc_id`: string
- time column: numeric seconds or parseable timestamp → convert to elapsed seconds per `(run_id, tc_id)`
- temperature column: numeric °C

If a run has **no thermocouple rows** at all, treat it as missing TC data.

### 0.4 Robust PDF extraction procedure
Handbooks vary; use a multi-pass approach:
1. **Search text** (e.g., `pdfplumber`) for keywords:
   - “preheat”, “ramp rate”, “°C/s”, “liquidus”, “TAL”, “time above liquidus”, “peak”, “conveyor speed”, “board length”, “dwell”.
2. If limits appear in tables, use a **table extractor** (Camelot/Tabula) on candidate pages.
3. Record extracted values with units. Convert to required units:
   - ramp limit: °C/s
   - TAL: seconds
   - conveyor speed: cm/min

Do not infer or “typical-industry” fill values.

---

## 1) Representative thermocouple selection (critical; used in Q01–Q03)

### 1.1 Handbook-first rule
Look for a handbook section like:
- “Thermocouple placement”, “Profile verification”, “Reference TC”, “Control thermocouple”, “Representative thermocouple”.

If the handbook **explicitly names** which TC to use (e.g., “Use TC3 at the cold spot”), then:
- Use exactly that TC for the question’s metric.

### 1.2 If handbook does NOT specify a single TC
Use a **spec-aware conservative representative**, so bounded-window specs cannot miss high-side violations:

- **Q01 ramp (max allowed):** representative TC per run = the TC with the **maximum** computed preheat ramp rate (worst-case for a max-limit).

- **Q02 TAL (must be within min/max):** representative TC per run = the TC that is **most critical vs the TAL window**:
  - if any TC violates the window, choose the TC with the **largest violation distance** to the nearest bound;
  - else choose the TC with the **smallest margin** to either bound.

- **Q03 peak minimum:** representative TC per run = the TC with the **minimum** peak temperature (worst-case vs minimum peak requirement).

Tie-break for determinism: smallest `tc_id` (lexicographic string order).

---

## 2) Q01 — Maximum temperature ramp rate during preheat (per run)

### 2.1 Extract from handbook (must)
Find and extract:
1. **Definition of preheat** (what phase of the profile counts).
2. **Applicable temperature region** for preheat (e.g., “from T_start to T_end”, or “ambient to soak start”, etc.).
3. **Ramp calculation equation** (typically slope):
   - `ramp = (T2 - T1) / (t2 - t1)` in °C/s
4. **Allowable ramp-rate limit** (°C/s).

Store the extracted ramp limit as `ramp_rate_limit_c_per_s`.

### 2.2 Compute ramp rate per TC within the preheat window
For each `(run_id, tc_id)`:
1. Sort samples by time.
2. Determine which samples are in the preheat temperature region defined by the handbook.
   - If the handbook defines preheat by temperature bounds `[T_low, T_high]`, filter to points where `T` is within bounds.
   - If the handbook defines by zones/time markers, derive the equivalent time window using temperatures and/or zone transitions if present.
3. For consecutive samples `(i, i+1)` within the window, compute segment slope:
   - `slope_i = (T[i+1] - T[i]) / (t[i+1] - t[i])`  (skip if `t[i+1] == t[i]`)
4. Keep only **positive heating slopes** if the handbook defines ramp as heating rate; otherwise follow handbook wording.
5. `max_preheat_ramp` = max of the eligible slopes.

If no eligible segment exists for a TC, that TC’s ramp is `null`.

### 2.3 Select representative TC per run
Use the representative TC rule in Section 1.
- Output `tc_id` and `max_preheat_ramp_c_per_s` for that run.

### 2.4 Determine violations
A run violates if:
- ramp limit is known **and** representative `max_preheat_ramp` is known **and** `max_preheat_ramp > limit`.

If limit is `null` or ramp is `null`, do **not** invent a violation; instead keep run out of `violating_runs` unless the task explicitly requires otherwise.

### 2.5 Output file
Write `/app/output/q01.json` with:
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

## 3) Q02 — Time Above Liquidus (TAL) per run

### 3.1 Extract from handbook (must)
Find and extract:
1. **Solder liquidus temperature** `T_liquidus` (°C) for the specified solder alloy.
2. TAL definition + how to measure:
   - whether TAL is total time above liquidus,
   - whether it’s continuous time, and whether multiple excursions are summed.
3. **TAL window/thresholds**:
   - required minimum TAL (seconds)
   - required maximum TAL (seconds)

### 3.2 Compute TAL per TC using crossing-time interpolation
For each `(run_id, tc_id)`:
1. Sort samples by time.
2. Identify intervals where `T` crosses `T_liquidus`.
3. Use linear interpolation for more accurate crossing times:
   - If `T[i] < L` and `T[i+1] >= L`, upward crossing at
     - `t_cross = t[i] + (L - T[i]) * (t[i+1]-t[i]) / (T[i+1]-T[i])`
   - If `T[i] >= L` and `T[i+1] < L`, downward crossing similarly.
4. Compute TAL according to handbook definition:
   - If TAL is **total time above liquidus**, sum durations of all above-liquidus segments.
   - If TAL must be a **single continuous span**, use the longest continuous above-liquidus span (only if handbook says so).

If no above-liquidus segment exists, TAL = `0.00` (unless handbook defines otherwise).
If sampling is insufficient to compute crossings reliably, set `tal_s = null`.

### 3.3 Select representative TC per run (handbook-driven)
Follow Section 1, with emphasis on Q02:
- If handbook names a “cold spot”/“acceptance TC” for TAL, use it.
- Else choose the TC that is **most critical vs the [min,max] TAL window** (can be either low-side or high-side critical).

### 3.4 Determine compliance status
If `tal_s`, `required_min_tal_s`, and `required_max_tal_s` are all non-null:
- compliant if `required_min_tal_s <= tal_s <= required_max_tal_s`
- else non-compliant

If any required threshold is `null` or `tal_s` is `null`, set status to `non-compliant` (cannot prove compliance without requirements/measurement).

### 3.5 Output file
Write `/app/output/q02.json` as a list of runs:
```json
[
  {
    "run_id": "R0001",
    "tc_id": "TC3",
    "tal_s": 42.50,
    "required_min_tal_s": 30.00,
    "required_max_tal_s": 90.00,
    "status": "compliant"
  }
]
```

---

## 4) Q03 — Peak temperature requirement per run

### 4.1 Extract from handbook (must)
Find peak temperature requirements, e.g.:
- minimum peak temperature (°C) OR
- minimum peak above liquidus (°C) OR
- a peak range [min, max]

The required output schema only requests `required_min_peak_c`, so:
- if the handbook specifies a range, extract the **minimum** as `required_min_peak_c`.

### 4.2 Compute peak per TC and select representative
For each `(run_id, tc_id)`:
- `peak_temp = max(T)`.

Representative TC per run:
- handbook-specified, else choose the **minimum peak** across TCs (worst-case vs minimum requirement).

### 4.3 Failing logic
A run fails if:
- it has **no thermocouple data**, OR
- `required_min_peak_c` is known and representative `peak_temp_c` is known and `peak_temp_c < required_min_peak_c`, OR
- `required_min_peak_c` is `null` or peak is `null` (cannot prove compliance → treat as failing per task instruction “If a run has no thermocouple data, it is failing”; extend conservatively when requirement is unknown).

### 4.4 Output file
Write `/app/output/q03.json`:
```json
{
  "failing_runs": ["R0002"],
  "min_peak_by_run": {
    "R0001": {"tc_id": "TC2", "peak_temp_c": 241.20, "required_min_peak_c": 235.00}
  }
}
```

---

## 5) Q04 — Conveyor speed feasibility per run

### 5.1 Extract from handbook (must)
Identify and extract:
1. **Board geometry parameter(s)** needed for speed feasibility (commonly board length in travel direction).
2. **Thermal dwell requirements** relevant to conveyor speed (e.g., total heated length / required dwell time window).
3. **Allowable conveyor speed constraints** (machine min/max speed, or process-derived limits).

### 5.2 Get actual conveyor speed from MES logs
From `mes_log.csv`, identify per `run_id` the recorded conveyor speed.
- Convert to **cm/min** if necessary.

### 5.3 Compute required minimum speed
Because the required output asks `required_min_speed_cm_min`, compute it from handbook constraints. Typical derivations (choose only what matches handbook wording):
- If handbook provides **maximum allowed dwell time** `t_max` over a known effective heated length `L_eff`:
  - `required_min_speed = (L_eff_cm / t_max_s) * 60`
- If handbook provides **minimum conveyor speed** directly, use it.
- If both machine and process constraints exist, use the most restrictive minimum.

If only a maximum speed is provided and no basis for a minimum exists, set `required_min_speed_cm_min = null` and determine `meets` using only what can be justified (e.g., machine allowable range if available).

### 5.4 Determine meets
Set `meets = true` only if:
- actual speed is non-null, and
- required minimum speed is non-null and `actual_speed >= required_min_speed`, and
- any other handbook-required constraints that can be checked are satisfied (e.g., actual speed within [min,max]).

If any required piece is missing, set `meets = false` (cannot prove feasibility).

### 5.5 Output file
Write `/app/output/q04.json` list sorted by run_id.

---

## 6) Q05 — Best run per board_family (quality + efficiency)

### 6.1 Join keys
Establish a reliable mapping:
- `run_id → board_family` (likely in `mes_log.csv` or `test_defects.csv`).

### 6.2 Quality scoring (from test_defects)
Define quality metrics strictly from available columns, e.g.:
- defect count per run,
- defect rate (defects / boards tested) if denominator exists.

Prefer (in order):
1. lowest defect rate,
2. lowest defect count,
3. if still tied, use secondary indicators available (e.g., severe defect types).

### 6.3 Efficiency scoring (from MES)
Use a measurable proxy available in `mes_log.csv`, e.g.:
- higher conveyor speed,
- shorter cycle time,
- higher throughput.

### 6.4 Pick best and runners-up
For each `board_family`:
- Rank runs by (quality best → efficiency best).
- `best_run_id` = top ranked.
- `runner_up_run_ids` = remaining run_ids sorted ascending (or sorted by rank, but keep deterministic; if rank order is used, document and apply consistently).

If a family has only one run, `runner_up_run_ids` should be `[]`.

### 6.5 Output file
Write `/app/output/q05.json` sorted by board_family.

---

## 7) Implementation checklist (to guarantee correctness)

- [ ] Extract and store handbook constants with page/section provenance in code comments.
- [ ] Validate thermocouple time monotonicity; sort and de-duplicate if needed.
- [ ] Use interpolation for TAL crossings.
- [ ] Apply representative TC selection rules exactly (handbook-first; else spec-aware “most critical”, especially for windowed TAL).
- [ ] Round floats to 2 decimals at final serialization step.
- [ ] Sort output structures exactly as required.
- [ ] Write JSON files to `/app/output/q01.json` … `/app/output/q05.json`.
