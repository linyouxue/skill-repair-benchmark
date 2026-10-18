---
name: reflow-profile-compliance-toolkit
description: Deterministic handbook-grounded retrieval and thermocouple computations for reflow profile compliance outputs such as ramp, TAL, peak, feasibility, and selection.
---



When to invoke:
1. Whenever the task involves reflow related questions from thermocouple data, MES data or defect data and handbook-defined regions/windows/limits.
2. Extract numeric limits / temperature regions / timing windows / margins / feasibility rules from handbook.pdf.
3. Compute run-level metrics from time–temperature thermocouple traces in a deterministic way.

This skill is designed to make the agent:
- retrieve the right definitions from the handbook, and
- compute metrics with predictable tie-breaks and interpolation.



## 0. Handbook retrieval is a prerequisite

Every downstream section (TC selection, ramp, TAL, peak, feasibility, best-run
ranking, anomaly scan) depends on handbook-grounded thresholds. If the
handbook was not read, those sections operate on fabricated inputs and the
anomaly scan cannot distinguish a wrong constant from a wrong rule. Do this
first.

**Reader retry queue** — try in order; move to the next on ImportError,
FileNotFoundError, empty-text extraction (< 50 chars returned), or encryption
error:

1. `pypdf`
2. `PyPDF2`
3. `pdfplumber`
4. `pdfminer.six`
5. Shell `pdftotext` (poppler-utils, via `subprocess`)
6. Claude's native PDF ingestion (attach the PDF file to the model turn)
7. OCR fallback — `pdf2image` + `pytesseract`

A `pip install <reader>` is an acceptable intermediate step. **At least 3
readers must be attempted** before concluding the handbook is unreadable.

**All-readers-fail rule:** if every reader genuinely fails, set every
handbook-derived `cfg` entry to `None` and emit `null` (not a pass/fail
verdict) for every downstream metric that depended on it. Do NOT substitute
"typical reflow" constants from memory — not even directionally plausible
ones. A memory-prior is a fabrication regardless of how it looks.

**Parameter-grounding comment discipline:** every numeric value in `cfg` must
have an adjacent code comment with the verbatim handbook sentence that
supports it. A bare number with no quote is suspect and must become `None`.

```python
# minimal sketch — see ../references/handbook-retrieval.md for the full
# branched algorithm (ImportError, empty text, encrypted, all-readers-fail)
text, attempts = try_read_handbook("/app/data/handbook.pdf")
if text is None:
    assert len(attempts) >= 3, "try more readers before giving up"
    cfg = {k: None for k in HANDBOOK_KEYS}
    cfg["_handbook_status"] = "unreadable"
else:
    cfg = extract_cfg_from_handbook_text(text)   # with grounding comments
    cfg["_handbook_status"] = "ok"
```

Decision rule: if after a failed handbook read your reasoning contains
"typical reflow is …", "the standard limit is …", or "I'll assume …", that
is a memory-prior substituting for the handbook — delete the constants, re-run
the retry queue, and if it still fails, emit `null`.

Read `../references/handbook-retrieval.md` when any threshold the task depends
on comes from a PDF handbook/spec. Skip when every needed parameter is given
inline in the task prompt or in a non-PDF structured file.



## Handbook "where to look" checklist (after retrieval succeeds)

Search the extracted handbook text for these common sections/tables:
- Thermal profile overview: defines "preheat", "soak", "reflow", "cooling".
- Ramp rate guidance: "ramp", "slope", "°C/s", "C/s".
- Liquidus & wetting time: "liquidus", "time above liquidus", "TAL", "wetting".
- Peak temperature guidance: "peak", "minimum peak", "margin above liquidus".
- Conveyor / dwell feasibility: "conveyor speed", "dwell time", "heated length", "zone length", "time-in-oven", oven zone-count prefixes (e.g. `8Z`, `10Z`).
- Thermocouple placement: "cold spot", "worst case", "representative sensor", named locations such as `largest_mass` / `coldest_point` / `smallest_mass`. Cross-check with the TC dataset's `location`/`position` column so the handbook's named placement maps to a concrete `tc_id`. The handbook may name a location for one metric only — do not assume it governs every metric.

Goal: extract a compact config object from the handbook and use it for all
computations. **Every value carries an adjacent handbook quote in a comment**
— if no quote can be produced, the value stays `None` and the dependent
metric emits `null`:

```python
cfg = {
    # Handbook §X.Y: "<verbatim preheat region sentence>"
    #   {"type":"temp_band", "tmin":..., "tmax":...}
    #   or {"type":"zone_band", "zones":[...]}
    #   or {"type":"time_band", "t_start_s":..., "t_end_s":...}
    "preheat_region": None,

    # Handbook §X.Y: "<verbatim ramp-rate limit sentence>"
    "ramp_limit_c_per_s": None,

    "tal_threshold_c_source": "solder_liquidus_c",   # if MES provides it
    # Handbook §X.Y: "<verbatim TAL lower bound sentence>"
    "tal_min_s": None,
    # Handbook §X.Y: "<verbatim TAL upper bound sentence>"
    "tal_max_s": None,

    # Handbook §X.Y: "<verbatim peak-margin sentence>"
    "peak_margin_c": None,

    # Per-metric representative-TC locations from the handbook. Each is
    # independent; leaving one None means fall back to generic per-TC
    # reduction for that metric. Do NOT reuse a named placement across
    # metrics without an explicit handbook sentence. See section 4.
    "ramp_rep_location": None,
    "peak_rep_location": None,
    "tal_rep_location":  None,

    # Conveyor feasibility rule-object; see section 6. Every parameter inside
    # must likewise carry a handbook quote.
    "conveyor_rule": None,
}
```

If the handbook provides multiple applicable constraints, implement all and
use the stricter constraint (document the choice in code comments).



Deterministic thermocouple computation recipes

1. Sorting and de-dup rules
Always sort samples by time before any computation:
```python
df_tc = df_tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")
```
Ignore segments where `dt <= 0` (non-monotonic timestamps).

2. Segment slope (ramp rate)
Finite-difference slope on consecutive samples:
- `s_i = (T_i - T_{i-1}) / (t_i - t_{i-1})` for `dt > 0`
- the "max ramp" is `max(s_i)` over the region.

Region filtering patterns:
- Temperature band region: only include segments where **both endpoints** satisfy `tmin <= T <= tmax`.
- Zone band region: filter by `zone_id in zones`.
- Time band region: filter by `t_start_s <= time_s <= t_end_s`.

Robust implementation (temperature-band example):
```python
def max_slope_in_temp_band(df_tc, tmin, tmax):
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    best = None
    for i in range(1, len(g)):
        dt = t[i] - t[i-1]
        if dt <= 0:
            continue
        if (tmin <= y[i-1] <= tmax) and (tmin <= y[i] <= tmax):
            s = (y[i] - y[i-1]) / dt
            best = s if best is None else max(best, s)
    return best  # None if no valid segments
```

3. Time above threshold with linear interpolation
For wetting/TAL-type metrics, compute time above a threshold `thr` using segment interpolation.

Two defensible interpretations of "time above threshold" exist — check the handbook wording before choosing:
- **Integral TAL** (default below): sum of every segment where temperature is above `thr`, including segments after a cooling discontinuity that briefly re-crosses. Matches "total time above the melting point".
- **Contiguous TAL** (first-crossing to last-crossing): one window per run, from the first upward crossing of `thr` to the last downward crossing. Matches "duration above liquidus" when the handbook describes a single reflow dwell.

If the integral interpretation causes a mass compliance failure (e.g. > 80% of runs fall outside the TAL window), re-read the handbook for which interpretation it endorses, AND confirm the window itself (`tal_min_s`, `tal_max_s`) has a handbook quote and is not a memory-prior, before letting the verdict cascade into ranking.

```python
def time_above_threshold_s(df_tc, thr):
    g = df_tc.sort_values("time_s")
    t = g["time_s"].to_numpy(dtype=float)
    y = g["temp_c"].to_numpy(dtype=float)
    total = 0.0
    for i in range(1, len(g)):
        t0, t1 = t[i-1], t[i]
        y0, y1 = y[i-1], y[i]
        if t1 <= t0:
            continue

        # fully above
        if y0 > thr and y1 > thr:
            total += (t1 - t0)
            continue

        # crossing: interpolate crossing time
        crosses = (y0 <= thr < y1) or (y1 <= thr < y0)
        if crosses and (y1 != y0):
            frac = (thr - y0) / (y1 - y0)
            tcross = t0 + frac * (t1 - t0)
            if y0 <= thr and y1 > thr:
                total += (t1 - tcross)
            else:
                total += (tcross - t0)
    return total
```

4. Representative sensor selection — per metric, not per run

**Default: different metrics have different governing worst-case TCs; use the same TC across metrics only when the handbook explicitly says so.** The handbook naming one location (e.g. `largest_mass`) is not a license to apply that one TC to every metric — it only governs the metric whose physical worst case matches the named location.

**Setup prose vs. reducer prose — classify every handbook sentence before mapping to `cfg["<metric>_rep_location"]`.** A handbook sentence can be either (i) a *measurement-setup* instruction naming where probes should be *placed* during a thermal survey, or (ii) a *reducer* instruction naming which TC should *govern* a specific metric. Only (ii) licenses setting `cfg["<metric>_rep_location"]`.

- **Setup prose — a noun phrase listing placements.** Signature: lists multiple locations without an imperative verb; often "may be measured by thermocoupling a lead on …", "probes shall be placed at …", "thermocouples on <loc A> and <loc B>". Examples: *"may be measured by thermocoupling a lead on the largest and smallest device"*, *"thermocouples on exposed and shielded locations"*. This tells the operator **where to place probes**; it does NOT designate any single TC as the representative for any single metric. Leave `cfg["<metric>_rep_location"] = None` and fall back to generic per-TC reduction.
- **Reducer prose — an imperative verb pointing at one metric and one location.** Signature: single location + metric name + imperative verb. Examples: *"use the coldest TC for the peak check"*, *"the ramp limit applies to the fastest-heating thermocouple"*, *"TAL is reported from the largest-mass sensor"*. This DOES license `cfg["<metric>_rep_location"] = <location>` for that one metric only.

If the only quotable sentence is setup prose, every `*_rep_location` stays `None`; the per-metric physical worst case (ramp → fastest-heating, peak → coolest-at-peak, TAL → both bounds via per-TC max/min) governs instead. See `../references/representative-tc-selection.md` for the full classifier with worked positive and negative examples.

Per-metric worst-case direction (quick table):

| Metric | Governing worst case | Reducer across matching TCs |
|---|---|---|
| Ramp (upper limit) | fastest-heating | `max`, tie-break smallest `tc_id` |
| Peak (minimum peak ≥ liquidus + margin) | coolest-at-peak | `min`, tie-break smallest `tc_id` |
| TAL upper bound (overshoot) | hottest / longest-above-liquidus | `max` TAL across TCs |
| TAL lower bound (minimum dwell) | coolest | `min` TAL across TCs |

Pre-coding enumeration: before writing any reducer, for each per-run question write a one-line comment stating (i) what "worst case" means physically for this metric, (ii) which handbook-named TC location (if any) satisfies it via a *reducer* sentence (not setup prose), and (iii) the verbatim handbook sentence that supports (ii). If (iii) is empty OR is setup prose, use generic per-TC reduction and leave `cfg["<metric>_rep_location"] = None`.

```python
# generic sketch — one reducer per metric, not one TC for the whole run
def reduce_per_metric(tc_rows, metric_fn, direction, rep_location):
    # direction: "max" (ramp, tal_upper) or "min" (peak, tal_lower)
    pool = tc_rows
    if rep_location is not None:
        matched = tc_rows[tc_rows["location"] == rep_location]
        if not matched.empty:
            pool = matched
    per_tc = [(metric_fn(grp), tc_id) for tc_id, grp in pool.groupby("tc_id")]
    per_tc = [(v, t) for v, t in per_tc if v is not None]
    if not per_tc:
        return (None, None)
    per_tc.sort(key=lambda x: ((-x[0] if direction == "max" else x[0]), x[1]))
    return per_tc[0]
```

**Trial alternative policies when any red-flag fires.** When the pre-ship scan reports any metric with `< 10 %` or `> 80 %` violators, do NOT ship on the first interpretation. Re-compute Q1/Q2/Q3 violator counts under at least two additional TC-selection policies — e.g. (α) a single consistent channel across metrics (handbook-named placement applied to all); (β) per-metric physical worst case per the table above; (γ) run-level max/min/mean across all TCs. The policy that both quotes a *reducer* sentence AND produces a plausible distribution (roughly 5–30 % non-compliance per metric for typical reflow data) is the one to ship. Record the three distributions in a comment next to the final choice.

Decision rule: if the handbook names `largest_mass`/"coldest point" only, use it ONLY for peak (and TAL lower bound if applicable). Do NOT reuse it for ramp or TAL upper bound — those need the fastest-heating / hottest channel. Consistency of `tc_id` across ramp/TAL/peak is NOT a goal.

Read `../references/representative-tc-selection.md` when the handbook mentions any TC-placement by name OR when the task has questions for more than one of ramp/TAL/peak. Skip when the handbook makes no placement statement anywhere and only one of ramp/TAL/peak is asked.

5. Peak and margin
Per TC: `peak_tc = max(temp_c)`. Run-level peak uses the per-metric reducer in section 4 with `direction="min"` and `rep_location = cfg["peak_rep_location"]`. Requirement: `required_peak = liquidus + peak_margin`.

6. Conveyor feasibility (grounded derivation, never fabricate)
Represent the handbook rule as a structured object and compute `required_min_speed_cm_min` only if every input is grounded in handbook text or oven_model geometry.

Grounded templates:
- Minimum dwell across effective heated length: `speed_max_cm_min = (L_eff_cm / t_min_s) * 60`
- Maximum time-in-oven across length:         `speed_min_cm_min = (L_eff_cm / t_max_s) * 60`

Deriving `L_eff_cm` when the handbook does not state it directly:
- Parse the oven_model string: a leading digit prefix is the zone count (e.g. `8Z…` → 8 zones, `10Z…` → 10 zones). Multiply zone count × handbook zone length.
- Use TAL min/max as the dwell bound only when the handbook ties conveyor dwell to TAL; otherwise find the handbook's own dwell/time-in-oven bound.

**Parameter-grounding prerequisite (applies to every variable in the chosen formula — `L_eff_cm`, `zone_length_cm`, `t_min_s`, `t_max_s`, any `loading_factor` / `boards_per_min` term):** each must have an adjacent code comment quoting the handbook sentence that defines it. If any variable is a bare number with no quote, treat the whole formula as fabricated: emit `required_min_speed_cm_min = null` and `meets = false`.

**Operator-precedence / dimensional check (PDF OCR is a source of operator drift — `×`, `÷`, parentheses are routinely dropped or misread).** After translating the handbook sentence to code, instantiate with one or two sample values and verify the units reduce to the expected output (`cm/min` for `required_min_speed_cm_min`). A dimensionless parameter (e.g. `loading_factor`) must enter as a divisor or multiplier such that the units balance. If `(boards/min) × cm / loading_factor` → `cm/min` only when `loading_factor` is dimensionless and placed as a divisor — if the computed magnitude is implausibly tiny or implausibly large with every run clearing/failing trivially, re-read the handbook and try the opposite arrangement (divisor ↔ multiplier) before shipping.

```python
# generic sketch — every input must carry a handbook quote in a comment
# Handbook §X.Y: "<verbatim zone length sentence>"
zone_length_cm = ...
# Handbook §X.Y: "<verbatim dwell / time-in-oven bound sentence>"
t_max_s = ...
zone_count = int(re.match(r"(\d+)Z", oven_model).group(1))
L_eff_cm   = zone_count * zone_length_cm
speed_min  = (L_eff_cm / t_max_s) * 60   # cm/min — dimensional check: cm / s * 60 = cm/min ✓
```

Hard rule — do NOT invent a formula. If `L_eff_cm` or the dwell bound cannot be grounded in the handbook or in oven_model geometry, emit:
- `required_min_speed_cm_min = null`
- `meets = false`
- a code comment stating which input was ungrounded.

Decision rule: if your own narrative contains "I'll assume…", "this seems suspicious", "probably all runs clear this", or "typical loading factor is …", that is a stop signal — the formula is fabricated. Return to the handbook (section 0 retry queue) or emit null.

Read `../references/conveyor-feasibility.md` when the handbook does not spell out a speed rule for the oven_model in use, when `L_eff_cm`/dwell bounds must be derived, OR when the handbook sentence used arithmetic operators (`×`, `÷`, parentheses) that may have drifted during OCR. Skip when the handbook gives a direct `oven_model → required_speed` mapping in plain-text table form.

7. Ranking / "best run" questions
When the task asks for the best / top / recommended / highest-yielding run (per family or overall), the prompt wording decides whether compliance is a hard gate or a quality signal:

- **Strict scope** ("best **compliant** run", "top performer that meets all specs"): rank only the mask=True subset where `ramp_ok AND tal_ok AND peak_ok AND feasibility_ok`; emit `null` for groups with no compliant runs.
- **Soft scope** ("best based on **quality and efficiency**", "recommended run", unqualified "top performer"): rank ALL runs in the group by a composite score (yield desc, throughput desc, `compliance_violation_count` asc as tie-break/penalty, `run_id` asc). Compliance is a signal, not a gate. Only emit `null` when the group has zero runs at all.

```python
# generic sketch — mode is "strict" or "graded"; both branches reuse the mask
mask = df["ramp_ok"] & df["tal_ok"] & df["peak_ok"] & df["feasibility_ok"]
df["_violations"] = (~df[["ramp_ok","tal_ok","peak_ok","feasibility_ok"]]).sum(axis=1)
pool = df[mask] if mode == "strict" else df
best = (pool.sort_values(
            quality_cols + (["_violations"] if mode == "graded" else []) + ["run_id"],
            ascending=[False]*len(quality_cols) + ([True] if mode == "graded" else []) + [True])
            .groupby(group_col).head(1))
```

Decision rule: a per-group sanity log reading `0/N compliant` is a stop signal — re-read the task prompt to decide strict vs. graded before writing output. Never pick a "best" run that is listed as a violator in your own earlier Q1–Q4 outputs if the prompt is in strict scope.

Read `../references/best-run-ranking.md` when the task asks for a best / top / recommended run per group AND either (i) the prompt wording is ambiguous between strict and graded, or (ii) a strict mask would wipe out ≥ 1 group. Skip when the prompt explicitly says "compliant" and every group has ≥ 1 compliant run.



Output construction guardrails

1. Sorting
- Lists: sort by primary ID (run_id / board_family) lexicographically.
- Dicts keyed by ID: emit in sorted key order.

2. Rounding and NaNs
- Round floats to 2 decimals.
- Never emit NaN/Inf; use `null`.

```python
def r2(x):
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return float(round(float(x), 2))
```

3. Missing thermocouple data OR ungrounded threshold
If a run has no TC records (or no valid segments for a metric), set numeric outputs to `null`, and avoid claiming "pass". The same rule applies when the handbook threshold for that metric is `None` (ungrounded): emit `null` for the metric, never a pass/fail verdict derived from a memory-prior.


## Minimal end-to-end scaffold

```python
import os, json, math, re
import pandas as pd

DATA_DIR = "/app/data"
OUT_DIR  = "/app/output"

runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))

runs["run_id"] = runs["run_id"].astype(str)
tc["run_id"]   = tc["run_id"].astype(str)
tc["tc_id"]    = tc["tc_id"].astype(str)

runs = runs.sort_values(["run_id"], kind="mergesort")
tc   = tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")

# 0) Retrieve handbook text via the reader retry queue (section 0 above /
#    ../references/handbook-retrieval.md). If all readers fail, every
#    handbook-derived cfg entry is None and every dependent metric emits null.
# 1) Build cfg with grounding-comment discipline (every value has a handbook
#    quote in a comment, or it stays None).
cfg = {...}

# 2) Compute per-run metrics deterministically with stable tie-breaks and
#    interpolation. For any metric whose threshold is None, emit null — do NOT
#    fall back to a memory-prior.
#    Use the PER-METRIC representative-TC rule (section 4) — ramp, TAL, peak
#    may select different tc_ids; that is expected.
# 3) Build JSON objects with sorted IDs and 2dp rounding.
# 4) For "best run" questions, pick strict vs. graded mode by prompt wording (section 7).
# 5) Write outputs into /app/output.
```

---

Sanity checks before writing outputs

Mechanical:
- ID fields are strings.
- Arrays sorted lexicographically.
- Floats rounded to 2 decimals.
- No NaN/Inf in JSON.
- Sensor selection uses deterministic tie-breaks AND respects the handbook's named placement for the metric whose physical worst case matches (section 4).
- Any "time above threshold" uses interpolation (not naive threshold counting).

Semantic — run in this order; do not skip:

- **(1) Handbook-grounding check (precedes everything else).** For every numeric threshold used in a verdict in this run's outputs (`ramp_limit_c_per_s`, `tal_min_s`, `tal_max_s`, `peak_margin_c`, `preheat_region` tmin/tmax, feasibility inputs `L_eff_cm` / `t_min_s` / `t_max_s` / `zone_length_cm` / any `loading_factor`), confirm there is an adjacent code comment quoting the handbook sentence that defines it. If any threshold is a bare number with no quote, set it to `None` and change the per-metric output to `null`. **On ANY mass-fail or near-zero signal flagged in checks 3/4 below, re-run this check first on the specific threshold driving the verdict** — if that threshold is ungrounded, it is the suspect, not the TC-selection rule or TAL interpretation; do NOT branch into (4) until (1) is clean.

- **(2) Narrative hedge check — scan for a class, not a fixed phrase list.** The hedge is any phrase in one of three classes, not a literal match from a catalogue:
    - *Outside-expectation adjectives* (synonym family of "suspicious"): "suspicious", "surprising", "unusual", "unusually extreme", "unexpected", "weird", "strange", "odd", "off", "implausible". A near-synonym from this family counts (e.g. "unusually extreme numbers" from iter_4 shares the mechanism with the catalogued "this seems suspicious" and must trip the scan).
    - *Hedging modals / memory-prior substitutions*: "probably", "might", "I'll assume", "I think", "typical reflow is …", "the standard limit is …", "the handbook doesn't say directly".
    - *Rationalisations that explain away an anomaly*: "real production anomaly", "systemic production pattern", "the data is just unusual", "that's just how reflow works", "the process is just running hot", "genuine over-cooked profiles".
   Any match: stop, re-open the handbook on the specific concept, and re-run the policy / interpretation decision — do NOT ship behind the hedge.

- **(3) Mechanical quantitative-anomaly scan (no judgement call).** Immediately after per-run verdicts are computed, emit a one-line summary of violator counts across the per-run questions, e.g. `Q1: X/N violators, Q2: Y/N violators, Q3: Z/N violators`. If any count is `< 0.10 * N` (near-zero) or `> 0.80 * N` (mass-fail), the scan has fired — no judgement call. First re-run check (1) on the threshold driving the fired verdict; only after (1) is clean, proceed to check (4).

- **(4) Paired quantitative-anomaly scan.** When two metrics share a selection rule (same TC-selection policy, same TAL interpretation, same feasibility arrangement) and show *asymmetric* flag rates — one metric `< 10 %` violators AND another `> 80 %` violators — the shared rule is miscalibrated per metric, not the data. Hard stop: re-examine the shared rule per metric (see `../references/representative-tc-selection.md` for the trial-alternative-policies procedure) before shipping. **Prerequisite:** confirm via (1) that both metrics' thresholds are handbook-grounded; if either is a memory-prior, the apparent asymmetry is an artifact of the wrong constant.

- **(5) Per-question spot-check must compare against an alternative interpretation.** An arithmetic spot check on the already-chosen policy only verifies *computation*, not *interpretation* — it is tautological against the policy that produced the number. For each per-run question type, re-compute the same representative cell under at least ONE alternative interpretation and compare: (α) different TC-selection policy for Q1/Q2/Q3 (fastest-heating vs. coolest vs. run-level max/min/mean); (β) different TAL window reading (integral vs. contiguous) for TAL; (γ) different operator arrangement (divisor ↔ multiplier) for feasibility. If the two outputs differ dramatically (e.g. 5/N vs. 51/N violators), the policy choice is driving the verdict and must be re-examined before shipping. For "best run" picks, verify compliance / non-null emission against the prompt mode (section 7).

## Common pitfalls

- **Hard-coding handbook constants from memory after a failed PDF read.** A single reader failure (ImportError, FileNotFoundError, empty text, encryption) is NOT a license to fall back to "typical reflow" priors (TAL 30–60 s, ramp 2 °C/s, margin +20 °C, invented `loading_factor`). The retry queue (section 0) requires ≥ 3 reader attempts, and if all genuinely fail, every handbook-derived threshold is `None` and every dependent verdict is `null`. Any `cfg` value lacking an adjacent handbook-quote comment is suspect regardless of how plausible it looks. See `../references/handbook-retrieval.md`.
- **Wrong representative-TC rule — four flavours of one mechanism.** All four share the same root: the handbook contains placement language that is syntactically close to a reducer policy, the agent locks on the first mapping that compiles, and no alternative TC-selection policy is trialled. (a) generic `max`/`min` across all TCs when the handbook names a placement; (b) applying one handbook-named TC uniformly to ramp AND TAL AND peak; (c) *inventing* a per-metric placement from memory without a handbook quote; (d) reading a *measurement-setup* sentence ("thermocouple a lead on the largest and smallest device") as a *per-metric reducer policy*. Fix: per-metric selection with a quoted reducer sentence (not setup prose) per placement, plus trial-alternative-policies when the mechanical anomaly scan fires. See section 4 and `../references/representative-tc-selection.md`.
- **Inventing a conveyor feasibility formula, fabricating its parameters, or shipping an OCR-drifted operator arrangement.** The grounded templates `(L_eff / t_bound) * 60` are the only sanctioned path; every parameter inside the chosen formula (`L_eff_cm`, `zone_length_cm`, `t_min_s`, `t_max_s`, `loading_factor`) must carry a handbook quote; AND the operator arrangement (divisor vs. multiplier) must survive a dimensional check (`cm/min` falls out of the formula with sample values). "Suspiciously tiny thresholds that every run clears", "a plausible-looking formula whose parameters have no handbook quote", and "a formula whose units don't balance when instantiated" are three signatures of the same failure. See `../references/conveyor-feasibility.md`.
- **Miscalibrated compliance filter in "best run" ranking.** Picking a violator from your own Q1–Q4 outputs (under-filter) and emitting `null` for most groups because a hard mask wiped them out (over-filter) are both failures of the same mechanism: not matching the filter strictness to the prompt wording. Section 7 names the two modes.
- **Shipping on an acknowledged anomaly without trialling an alternative interpretation.** Hedge-class phrases (adjectives / modals / rationalisations — see semantic check 2), isolated quantitative anomalies (near-zero or mass-fail from check 3), AND paired asymmetric anomalies across metrics sharing a rule (check 4) are all stop signals of one class: the threshold is ungrounded, the policy is miscalibrated, or the interpretation is wrong — not the data. The resolution is NOT an arithmetic re-check on the already-chosen policy (that is tautological) — it is re-computing the same cell under an alternative interpretation and comparing (check 5).
