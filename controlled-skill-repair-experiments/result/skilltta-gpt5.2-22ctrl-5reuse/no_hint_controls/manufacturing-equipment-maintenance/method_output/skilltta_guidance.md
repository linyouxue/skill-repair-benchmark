# SKILL.md

## When to use
Use this skill when you must answer manufacturing reflow-process compliance questions by **deriving numeric results from provided datasets** (e.g., thermocouple time/temperature traces, MES logs, defects) and **authoritative rules embedded in a handbook PDF**, then write results to **strictly formatted JSON output files**.

Before acting, gather and confirm:
- **Handbook definitions and limits** needed for each metric (e.g., how “preheat” is defined, what temperature window qualifies, ramp-rate formula, TAL definition/window and thresholds, peak temp requirements, conveyor speed constraints driven by board geometry/dwell).
- **Dataset schema and joins**:
  - Thermocouple table: run identifiers, thermocouple identifiers, timestamps/elapsed time, temperatures, and any columns indicating zone/phase.
  - MES/test defect tables: run metadata (board family, speed, recipe, conveyor settings), and quality indicators needed for “best run” selection.
- **Output contract**: required file paths, JSON shape, rounding rules, sorting rules, allowed `null`s, and what constitutes failing/compliance when data is missing.

## Possible Failure Modes
- **Hallucinating handbook parameters**: inventing limits/definitions (preheat window, TAL range, liquidus, peak requirement) instead of extracting them from the PDF.
- **Using the wrong thermocouple selection rule**: picking the maximum/average TC arbitrarily when the handbook specifies a “most representative” sensor (e.g., coldest spot, hottest spot, center-of-board, or a named TC position).
- **Incorrect ramp calculation**:
  - Computing overall slope across the entire preheat region instead of the **maximum local ramp rate** within the defined window.
  - Mixing units (minutes vs seconds) or using non-monotonic timestamps without sorting.
  - Not restricting calculations to the handbook’s specified temperature region/time window.
- **Incorrect TAL calculation**:
  - Using the wrong liquidus temperature or misreading the handbook TAL window (e.g., counting time above liquidus across the whole profile vs only the reflow segment if specified).
  - Mishandling threshold crossings (linear interpolation vs nearest-sample assumption) inconsistently with handbook guidance.
- **Peak temperature compliance mistakes**:
  - Comparing against the wrong bound (min vs max) or using the wrong TC statistic (min peak across TCs vs max peak).
  - Forgetting the rule “missing thermocouple data ⇒ failing”.
- **Conveyor speed feasibility errors**:
  - Not converting units (e.g., cm/min vs mm/s) per handbook.
  - Ignoring geometry/dwell constraints (length, required dwell time, heated length) and just checking a generic speed range.
- **JSON contract violations**:
  - Wrong keys, wrong types (string vs number), missing required fields, unsorted arrays, not rounding to 2 decimals, or not using `null` where required.
- **Non-reproducible/opaque derivations**: not leaving an auditable trail of which handbook clause and which dataset columns were used, making it hard to justify results.

## Possible procedures
1. **Ingest and inspect inputs**
   - Load CSVs with explicit dtypes (ensure run_id/tc_id remain strings).
   - Inspect thermocouple columns: locate time base (timestamp or elapsed seconds) and temperature column; confirm sampling cadence and presence of duplicates.
   - Extract run-level settings (e.g., conveyor speed) from MES logs (or wherever it resides).

2. **Extract rules from the handbook PDF (do this first for each question)**
   - Search the PDF for keywords: “preheat”, “ramp”, “°C/s”, “TAL”, “time above liquidus”, “liquidus”, “peak temperature”, “conveyor”, “dwell”, “board length/geometry”.
   - Record (for internal use) the exact clause for:
     - Metric definition (what to measure).
     - Applicable temperature/time region.
     - Equation (including any max-of-window rule).
     - Limit/threshold (min/max).
     - Thermocouple selection rule (“most representative”).
   - Decision point: if the handbook gives multiple alternatives (by product, alloy, board family, etc.), identify which contextual variable (board_family, alloy type, recipe) selects the correct one; otherwise, apply the handbook’s “default/standard” explicitly.

3. **Q1: Maximum preheat ramp rate per run**
   - Filter each run’s trace to the handbook-defined **preheat region** (by temperature bounds and/or zone/time markers).
   - Ensure samples are time-sorted; drop or consolidate duplicate timestamps.
   - Compute local ramp rates:
     - Typically: \(\Delta T / \Delta t\) between consecutive points; keep only positive \(\Delta t\).
     - If handbook implies smoothing/averaging window, apply it consistently.
   - Take the **maximum ramp** within the preheat region.
   - Thermocouple selection:
     - For runs with multiple TCs, compute each TC’s max ramp, then choose the “representative” TC according to handbook rule (not arbitrary max/min).
   - Compare run’s selected max ramp to the handbook limit; collect violating run_ids.
   - Recovery check: if preheat region has insufficient points or missing time/temperature, set values to `null` and treat compliance accordingly per contract.

4. **Q2: Time Above Liquidus (TAL) per run**
   - Extract liquidus temperature from the handbook (or alloy-specific section).
   - Identify the TAL measurement window per handbook (may be “entire profile” or bounded around reflow).
   - For each run and each eligible TC:
     - Determine total time where \(T \ge T_{liquidus}\).
     - Handle boundary crossings carefully:
       - If handbook requires interpolation, linearly interpolate crossing times between samples.
       - Otherwise, use sample-based approximation (document internally).
   - Apply handbook min/max TAL thresholds; set `status` accordingly.
   - Decide which TC to report per run:
     - If the output expects one row per run, select the representative TC per handbook.
     - If multiple rows are allowed/expected, ensure formatting matches the contract (the target contract dictates shape).
   - Use `null` for TAL or thresholds if the handbook or data does not provide enough information (and ensure status logic follows the contract).

5. **Q3: Peak temperature requirement per run**
   - Extract peak requirement(s) from the handbook (minimum peak, and any maximum peak if stated—only enforce what is asked).
   - For each run:
     - If no thermocouple records exist: mark run failing.
     - Otherwise compute each TC’s peak temperature, then select the statistic required (e.g., minimum of TC peaks if ensuring all locations reach minimum).
   - Output the failing run list and per-run chosen TC/peak and required minimum peak.
   - Recovery check: if temperature column is partially missing, compute peak on available points and note missingness by using `null` where a value can’t be derived.

6. **Q4: Conveyor speed feasibility**
   - Extract from handbook:
     - Board geometry parameter(s) needed (length/thermal mass proxy, etc.).
     - Thermal dwell requirement(s) (minimum time in certain zones or heated length).
     - Allowed conveyor speed limits or formula.
   - Pull actual speed per run from MES logs (confirm unit).
   - Compute required min speed (or min/max range) based on geometry/dwell constraints as specified.
   - Compare actual vs required; emit boolean `meets`.
   - Decision point: if geometry is per board_family or board_id, join accordingly; if missing, emit `null` required speed and set `meets` to `false` unless the contract states otherwise.

7. **Q5: Best run per board_family (quality + efficiency)**
   - Define measurable proxies from available data (must be grounded in data, not guesses), e.g.:
     - Quality: defect count/rate from test_defects, compliance status from Q1–Q4, yield indicators.
     - Efficiency: throughput proxies such as higher feasible conveyor speed, shorter cycle time, fewer rework flags.
   - For each board_family:
     - Filter candidate runs.
     - Rank runs with a transparent tie-breaker order (e.g., prioritize compliance/quality first, then efficiency).
     - Select `best_run_id`; set remaining as `runner_up_run_ids` sorted ascending.
   - Recovery check: if a board_family has no runs or no usable quality signals, use `null`/empty arrays per output contract rather than inventing a choice.

8. **Output writing**
   - Write each answer to the specified `/app/output/q0X.json` path.
   - Round floats to **2 decimals** at the final serialization step (avoid compounding rounding during intermediate calculations).
   - Sort:
     - Arrays by run_id/board_family/board_id ascending as required.
     - Object keys: ensure deterministic ordering if the evaluator is strict (serialize with sorted keys when appropriate, while still matching the required structure).

## Verification Checklist
- [ ] Handbook evidence extracted for every required parameter: **definition**, **window/region**, **equation**, **limit/threshold**, and **thermocouple selection rule**; no values are assumed without a source.
- [ ] Thermocouple computations:
  - [ ] Time axis sorted; units consistent (seconds vs minutes).
  - [ ] Preheat filtering matches handbook’s region exactly.
  - [ ] Ramp uses correct \(\Delta T/\Delta t\) convention and selects the correct “maximum” notion.
  - [ ] TAL uses correct liquidus temperature and correct crossing/time accumulation method.
  - [ ] Peak temperature uses the correct statistic (per-run min/selected TC) and missing TC data causes failure where required.
- [ ] Conveyor speed:
  - [ ] Actual speed sourced from logs; unit converted to **cm/min** (or contract-required units).
  - [ ] Required speed derived from handbook geometry/dwell constraints; missing geometry handled with `null` + contract-consistent `meets`.
- [ ] Output files exist at exactly:
  - [ ] `/app/output/q01.json`
  - [ ] `/app/output/q02.json`
  - [ ] `/app/output/q03.json`
  - [ ] `/app/output/q04.json`
  - [ ] `/app/output/q05.json`
- [ ] JSON format compliance:
  - [ ] Keys and value types match the schema exactly (`true/false`, strings, numbers, `null`).
  - [ ] Floats rounded to **2 decimals**.
  - [ ] Arrays sorted ascending by required field(s); runner-up lists sorted.
  - [ ] No extraneous fields added.
- [ ] Non-copying guard: no hardcoded constants taken from retrieved examples; all numeric limits come from the handbook or datasets.
- [ ] Recovery check: if any metric cannot be computed due to missing/ambiguous data, outputs use `null` (not fabricated numbers) and downstream status/failing logic follows the contract.
