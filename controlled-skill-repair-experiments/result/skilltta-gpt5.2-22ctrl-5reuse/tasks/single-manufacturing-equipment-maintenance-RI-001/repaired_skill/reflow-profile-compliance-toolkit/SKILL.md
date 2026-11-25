---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval and thermocouple computations for reflow profile compliance outputs such as ramp, TAL, peak, feasibility, and selection.
---

# Reflow Profile Compliance Toolkit

## When to invoke

Use this skill whenever you must:
1) extract definitions/limits/windows from `handbook.pdf`,
2) compute compliance metrics from `thermocouples.csv` and `mes_log.csv`, and
3) emit deterministic JSON deliverables without guessing.

Core principle: **handbook.pdf is authoritative**. Do not hard-code numeric limits or assume industry defaults.

---

## Deliverables & completion conditions (trial-critical)

When the task asks Q1–Q5 artifacts, you must write **all** of the following files (exact names) under `/app/output/`:

1) `/app/output/q01.json` (object)
2) `/app/output/q02.json` (array)
3) `/app/output/q03.json` (object)
4) `/app/output/q04.json` (array)
5) `/app/output/q05.json` (array)

Completion conditions:
- **Schema adherence:** keys and nesting must match the prompt exactly; output must be valid JSON.
- **No hallucination:** any requirement/limit/window/margin must be extracted from `handbook.pdf`. If not determinable, emit `null`.
- **Rounding:** round all float outputs to **2 decimals**.
- **Sorting:**
  - arrays sorted by `run_id` / `board_family` ascending (lexicographic),
  - dicts keyed by `run_id` emitted in ascending key order.
- **Per-entity row expectations (remove ambiguity):**
  - Q02 array should contain **exactly one record per run_id** (representative `tc_id` per run).
  - Q04 array should contain **exactly one record per run_id**.
  - Q05 array should contain **exactly one record per board_family**.
- **Missing data handling:**
  - never emit NaN/Inf; use `null`,
  - do not claim compliance when required values are `null`,
  - special rule from the trial: **if a run has no thermocouple data, it is failing for Q3**.
- **Empty arrays:** represent as `[]` (do not include placeholder empty strings).

---

## Run universe (what counts as “each run”)

Unless the prompt explicitly states otherwise, use:
- `run_ids = sorted(unique run_id from mes_log.csv)`.

If `mes_log.csv` is missing `run_id` or is empty, fall back to:
- `run_ids = sorted(unique run_id from thermocouples.csv)`.

This ensures Q02/Q04 output “one record per run” is well-defined.

---

## Handbook extraction checklist (make a config)

Search the handbook for:
- Definitions: “preheat”, “soak”, “reflow”, “cooling”.
- Ramp/slope guidance: “ramp rate”, “slope”, “°C/s”, and whether the limit applies to **ramp-up only** or **absolute slope**.
- TAL guidance: “liquidus”, “time above liquidus”, “TAL”, whether it is **at/above** or **above** liquidus, and any **measurement window** boundaries.
- Peak guidance: “peak temperature”, “minimum peak”, “maximum peak”, “margin above liquidus”.
- Conveyor feasibility: “conveyor speed”, “heated length”, “dwell time”, “time in oven”, any explicit min/max speed.
- Thermocouple representativeness: “cold spot”, “hottest spot”, “largest thermal mass”, “representative thermocouple”.

Extract a compact `cfg` used consistently across Q1–Q4:

```python
cfg = {
  # Preheat definition / region mapping used for ramp.
  # One of:
  # {"type":"temp_band", "tmin":..., "tmax":...}
  # {"type":"time_band", "t_start_s":..., "t_end_s":...}
  # {"type":"zone_band", "zones":[...]}
  "preheat_region": {...},

  "ramp_rate_limit_c_per_s": ...,
  # Whether ramp limit is for ramp-up only (max positive slope) or absolute slope magnitude.
  # Must come from handbook wording; if not determinable, set null and default to max positive slope.
  "ramp_use_abs": True | False | None,

  # TAL
  "liquidus_temp_c": ...,                 # from handbook (or handbook -> MES field mapping)
  "tal_min_s": ...,
  "tal_max_s": ...,
  "tal_inclusive": True,                  # True if TAL is defined as at/above liquidus
  # Optional TAL measurement window, only if handbook defines one beyond just "above liquidus":
  # {"type":"time_band", "t_start_s":..., "t_end_s":...}
  # {"type":"temp_band", "tmin":..., "tmax":...}  # e.g., measure only within reflow/peak region
  # {"type":"zone_band", "zones":[...]}
  "tal_window": {...} | None,

  # Peak requirements (handbook may define absolute values, a window, or derived from liquidus)
  "peak": {
     "mode": "absolute" | "window" | "liquidus_plus_margin" | "unknown",
     "min_c": ...,                        # if provided
     "max_c": ...,                        # if provided
     "margin_c": ...,                     # only if handbook explicitly defines peak = liquidus + margin
  },

  # Conveyor rule (keep it structured; do not invent constraints)
  "conveyor": {
     "mode": "explicit_speed_window" | "explicit_min_speed" | "explicit_max_speed" |
             "max_time_in_oven" | "min_dwell_time" | "unknown",
     "min_speed_cm_min": ...,             # if available
     "max_speed_cm_min": ...,             # if available
     "L_eff_cm": ...,                     # effective heated length if handbook provides it
     "t_max_s": ...,                      # maximum allowed time in oven (if provided)
     "t_min_s": ...,                      # minimum required dwell time (if provided)
  },

  # Representative thermocouple rule text extracted from handbook
  "rep_tc_rule": {
     "ramp": "...", "tal": "...", "peak": "..."
  }
}
```

If multiple applicable constraints exist, implement all and treat a run as meeting requirements only if it meets every applicable constraint.

---

## Deterministic thermocouple computation recipes

### 1) Sorting, types, and invalid segments
Always sort by time before computations and ignore non-monotonic intervals.

```python
import math

def r2(x):
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return float(round(float(x), 2))

# Always per (run_id, tc_id)
df_tc = df_tc.sort_values(["run_id", "tc_id", "time_s"], kind="mergesort")
```

For any segment between consecutive samples, ignore if `dt <= 0`.

### 2) Ramp rate (finite difference)
Handbook equation is typically:
- `s_i = (T_i - T_{i-1}) / (t_i - t_{i-1})` for `dt > 0`
- max ramp = `max(s_i)` within the handbook-defined “preheat” region.

Important: the handbook may define ramp limit as either:
- **ramp-up only** (use maximum **positive** slope), or
- **absolute slope** (use maximum `abs(s_i)`).

Do not guess; extract the wording. If not determinable, default to max positive slope (still an auditable choice).

Temperature-band example (both endpoints must be inside band unless handbook states otherwise):

```python
def max_slope_in_temp_band(df_one_tc, tmin, tmax, use_abs=False):
    g = df_one_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    best = None
    for i in range(1, len(g)):
        dt = t[i] - t[i-1]
        if dt <= 0:
            continue
        if (tmin <= y[i-1] <= tmax) and (tmin <= y[i] <= tmax):
            s = (y[i] - y[i-1]) / dt
            s = abs(s) if use_abs else s
            best = s if best is None else max(best, s)
    return best  # None if no valid segments
```

### 3) TAL / time-above-threshold with linear interpolation (inclusive-capable)
The handbook may define TAL as **time at/above** liquidus or **strictly above** liquidus.
- If the handbook states “at or above” liquidus, use `>=` (inclusive).
- If the handbook states “above” liquidus, use `>` (strict).
- If not explicit, default to **inclusive (>=)** to avoid undercounting plateaus.

```python
def time_above_threshold_s(df_one_tc, thr, inclusive=True):
    g = df_one_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    total = 0.0

    def above(v):
        return v >= thr if inclusive else v > thr

    for i in range(1, len(g)):
        t0, t1 = t[i-1], t[i]
        y0, y1 = y[i-1], y[i]
        if t1 <= t0:
            continue

        a0, a1 = above(y0), above(y1)

        # Entire segment above
        if a0 and a1:
            total += (t1 - t0)
            continue

        # Entire segment below
        if (not a0) and (not a1):
            continue

        # Crossing segment: linearly interpolate crossing time.
        # If y0 == y1, it cannot cross unless exactly at thr; but that case is handled above.
        if y1 == y0:
            continue

        frac = (thr - y0) / (y1 - y0)
        tcross = t0 + frac * (t1 - t0)

        # Determine which side is above
        if a0 and (not a1):
            total += (tcross - t0)
        elif (not a0) and a1:
            total += (t1 - tcross)

    return total
```

If the handbook defines a **TAL measurement window** (e.g., only within certain zones or between two times), apply that window **before** calling `time_above_threshold_s`:
- Filter to the window, and if window boundaries fall between samples, add interpolated boundary points (deterministically) so the integration is not biased.
- If you cannot apply the handbook window deterministically, set TAL to `null`.

---

## Representative thermocouple selection (handbook-first, deterministic fallback)

**Primary rule:** follow the handbook’s thermocouple selection guidance (e.g., “cold spot”, “largest thermal mass”, “hottest point”).

If (and only if) the handbook does not define how to pick the representative TC for a given metric, use deterministic fallbacks:

### A) One-sided limit (e.g., ramp must be <= limit)
- Representative TC = the one with the **maximum** computed value (worst-case toward violating the limit).
- Tie-break: choose lexicographically smallest `tc_id`.

### B) Windowed requirement (e.g., TAL must be within [min, max])
Compute the metric for every TC; then select:
1) If any TC is **non-compliant**, select the TC with the **largest violation magnitude**:
   - if `v < min`: violation = `min - v`
   - if `v > max`: violation = `v - max`
2) Else (all compliant), select the TC with the **smallest margin to a boundary**:
   - margin = `min(v - min, max - v)`
3) Tie-break: smallest `tc_id`.

This produces a conservative, auditable, deterministic “most critical” TC without contradicting any explicit handbook rule.

### C) Peak requirement possibilities
Peak limits may be:
- minimum only,
- maximum only,
- a window [min, max], or
- derived (liquidus + margin) only if the handbook explicitly defines it.

Select the representative TC using the same **one-sided/windowed** logic as above (most critical relative to the applicable limits).

---

## Q1 guidance: max preheat ramp per run
- Use handbook definition of preheat (temp band / time band / zones).
- Use handbook ramp equation and interpret whether it is ramp-up only vs absolute slope.
- Compute max ramp within preheat per TC, then select representative TC per the selection rules above.
- Output:
  - `ramp_rate_limit_c_per_s` from handbook (or `null` if not determinable)
  - `max_ramp_by_run[run_id] = { tc_id, max_preheat_ramp_c_per_s }`
  - `violating_runs`: runs where representative ramp is not null and `ramp > limit`.

If there are no valid segments for preheat ramp in a run, emit `null` ramp for that run.

---

## Q2 guidance: TAL per run (one row per run)
- Liquidus temperature must come from the handbook (or a handbook-defined mapping to a MES field).
- TAL window (where TAL is measured) and min/max thresholds must come from the handbook.
- If the handbook defines a TAL measurement window beyond “time above liquidus”, apply it deterministically (clip/filter) before time integration; otherwise compute TAL over the full curve using the threshold crossings.
- Compute TAL per TC using `time_above_threshold_s(..., inclusive=cfg["tal_inclusive"])`.
- Select representative TC handbook-first; otherwise use windowed fallback above.
- Status:
  - `compliant` only if TAL is not null and `tal_min_s <= TAL <= tal_max_s`.
  - otherwise `non-compliant`.

Output requirements:
- Emit an array sorted by `run_id`.
- Emit **exactly one record per run_id**, using the representative `tc_id`.
- Include `required_min_tal_s` and `required_max_tal_s` in every row (or `null` if not determinable from the handbook).

---

## Q3 guidance: peak temperature requirement per run
- Extract peak requirement(s) exactly as the handbook defines them.
  - If handbook gives absolute min and/or max peak, use those.
  - If handbook defines a derived requirement (e.g., `peak >= liquidus + margin`), use that derivation only if explicitly stated.
- Compute `peak_temp_c = max(temp_c)` per TC.
- Determine compliance against **all** applicable peak constraints.
- Representative TC: handbook-first; otherwise choose the “most critical” TC relative to the applicable constraint(s).
  - For a minimum-peak requirement, this typically becomes the **minimum peak** across TCs.
- Trial rule: if a run has **no thermocouple data**, it is failing.

Schema note:
- Q3 JSON schema only includes `required_min_peak_c`. If the handbook also defines a max peak, you must still enforce it for pass/fail, but you cannot add extra keys to the output; keep the max internally.

---

## Q4 guidance: conveyor speed feasibility per run (actionable and schema-aligned)

### 1) Interpret constraints correctly
Let `time_in_oven = L_eff_cm / speed_cm_s` (equivalently `speed_cm_min = (L_eff_cm / time_s) * 60`).

From handbook constraints:
- **Maximum allowed time in oven** (`time_in_oven <= t_max_s`) implies a **minimum speed**:
  - `speed_min_cm_min = (L_eff_cm / t_max_s) * 60`
- **Minimum required dwell time** (`time_in_oven >= t_min_s`) implies a **maximum speed**:
  - `speed_max_cm_min = (L_eff_cm / t_min_s) * 60`
- If handbook provides an explicit speed window `[min, max]`, use it directly.

### 2) Map to Q4 schema
Q4 schema only has `required_min_speed_cm_min`. Populate it when determinable:
- If handbook provides speed window: `required_min_speed_cm_min = min_speed`.
- If handbook provides explicit min speed: `required_min_speed_cm_min = that min`.
- If handbook provides only `t_max_s` (max time): compute `required_min_speed_cm_min`.
- If handbook provides only `t_min_s` (min dwell => max speed), `required_min_speed_cm_min` is `null` (because the constraint is on maximum speed, not minimum).

### 3) Determine `actual_speed_cm_min` without guessing units
- Use MES field(s) and their documented units (from handbook, MES header conventions, or explicit column naming like `*_cm_min`, `*_m_min`).
- If units cannot be determined, set `actual_speed_cm_min = null`.

### 4) Determine `meets`
`meets` must reflect **all applicable handbook constraints** that can be evaluated:
- If actual speed is null → `meets = false`.
- If handbook gives min speed → require `actual >= min`.
- If handbook gives max speed → require `actual <= max`.
- If handbook gives both → require within window.
- If handbook constraints cannot be evaluated due to missing handbook parameters (e.g., `L_eff_cm` missing for a time-based rule) → `meets = false`.

Output requirements:
- Emit an array sorted by `run_id`.
- Emit **exactly one record per run_id**.

---

## Q5 guidance: deterministic best-run selection per board_family (no invented weights)

Goal: select the best run per `board_family` based on **quality first**, then **efficiency**, using only available columns.

### 1) Eligibility gate (deterministic)
A run is eligible iff:
- It has required computed metrics (no required nulls), and
- It is compliant for Q1–Q4 per the derived outputs.

If some question’s result is missing/unknown (`null`) in a way that prevents a compliance decision, treat the run as **not eligible**.

### 2) Quality metric (use only what exists)
From `test_defects.csv`, derive a single numeric `defect_score` per run deterministically:
- If a column named like `defect_count`, `total_defects`, or `defects` exists, use it.
- Else, sum all numeric defect columns excluding identifiers (e.g., excluding `run_id`, `board_family`, timestamps).
- If no numeric defect signal exists, `defect_score = null` (cannot rank by quality).

### 3) Efficiency metric (throughput proxy)
Use an MES-derived throughput proxy only if present and comparable across runs:
- Prefer `actual_speed_cm_min` (from Q4) if available.
- Else, if MES has a clear speed field with known units, use converted cm/min.
- Else, efficiency is null.

### 4) Ranking rule per board_family
For each board_family, among **eligible** runs with non-null `defect_score`:
1) ascending `defect_score` (fewest defects)
2) descending efficiency metric (e.g., higher conveyor speed) if available; if efficiency is null for all eligible runs, skip this key
3) tie-break: ascending `run_id`

### 5) runner_up_run_ids must list “other run_ids”
Per prompt wording, `runner_up_run_ids` should be **all other run_ids for that board_family besides best_run_id**, sorted ascending, regardless of eligibility.
- If `best_run_id` is `null`, then `runner_up_run_ids` should contain **all** run_ids for the family (sorted).

If no eligible run has a usable `defect_score`, set `best_run_id = null`.

Never invent weights or composite formulas not grounded in available columns.

---

## Output construction guardrails

### Sorting
- Lists: sort by primary ID (`run_id` / `board_family`) lexicographically.
- Dicts keyed by run_id: construct in sorted order before JSON dump.
- Nested lists like `runner_up_run_ids`: sort lexicographically.

### Nulls / NaN
- Use `null` for missing/uncomputable values.
- Never emit NaN/Inf.

### Deterministic tie-breaks
- Always break ties by lexicographically smallest `tc_id` (or `run_id` as specified).

---

## Minimal end-to-end scaffold

```python
import os, json, math
import pandas as pd

DATA_DIR = "/app/data"
OUT_DIR  = "/app/output"

runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))
defs = pd.read_csv(os.path.join(DATA_DIR, "test_defects.csv"))

# Normalize IDs as strings
for df in (runs, tc, defs):
    if "run_id" in df.columns:
        df["run_id"] = df["run_id"].astype(str)
if "tc_id" in tc.columns:
    tc["tc_id"] = tc["tc_id"].astype(str)

# Stable sorting
runs = runs.sort_values(["run_id"], kind="mergesort")
tc   = tc.sort_values(["run_id", "tc_id", "time_s"], kind="mergesort")

# 0) Determine run universe
if "run_id" in runs.columns and len(runs):
    run_ids = sorted(runs["run_id"].unique().tolist())
else:
    run_ids = sorted(tc["run_id"].unique().tolist())

# 1) Extract cfg from handbook.pdf (definitions, regions, limits, windows)
cfg = {...}

# 2) Compute per-run metrics with interpolation and handbook-first selection
# 3) Build q01..q05 JSON objects with sorting + r2 rounding
# 4) Write: /app/output/q01.json ... /app/output/q05.json
```

Sanity checks before writing outputs:
- All required files are created.
- Arrays and dict keys are sorted.
- Floats are rounded to 2 decimals via `r2`.
- Representative TC selection follows handbook, else uses the deterministic fallback.
- Q02/Q04 contain exactly one record per run_id.
