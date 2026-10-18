---
name: reflow-machine-maintenance-guidance
description: Guidance for answering reflow machine maintenance questions from thermocouple data, MES data, defect data and reflow technical handbooks — concepts, calculations, thresholds, and cross-validation between handbook and datasets.
---

This skill should be considered when you need to answer reflow equipment maintenance questions based on thermocouple data, MES data, defect data, and reflow technical handbooks. Based on the questions, first retrieve related info from the handbook and corresponding datasets. Most frequently asked concepts include preheat, soak, reflow, cooling, ramp, slope, C/s, liquidus and wetting time, ramp rate guidance, time above liquidus, TAL, peak temperature guidance, minimum peak, margin above liquidus, conveyor speed, dwell time, heated length, zone length, time-in-oven, thermocouple placement, cold spot, worst case, representative sensor (including named locations such as `largest_mass`, `smallest_mass`, `coldest_point`), numeric limits, temperature regions, etc. If the handbook provides multiple values or constraints, implement all and use the stricter constraint or the proper value.

Handbook retrieval is a prerequisite (do this first). Every numeric threshold, region, window, margin, and feasibility rule used below is a handbook quote — not a memory-prior. Before any computation, read the handbook PDF with a reader-retry queue: `pypdf` → `PyPDF2` → `pdfplumber` → `pdfminer.six` → shell `pdftotext` → Claude native PDF ingestion → OCR (`pdf2image` + `pytesseract`). On ImportError, FileNotFoundError, empty-text extraction (< 50 chars), or encryption error, move to the next reader. A `pip install <reader>` is an acceptable intermediate step. At least 3 readers must be attempted before concluding the handbook is unreadable. If all genuinely fail, set every handbook-derived `cfg` entry to `None` and emit `null` (not a pass/fail verdict) for every downstream metric that depended on it — do NOT substitute "typical reflow" constants from memory, even directionally plausible ones. For every value kept in `cfg`, place an adjacent code comment with the verbatim handbook sentence that supports it; a bare number with no quote is suspect and must become `None`. See `../references/handbook-retrieval.md` for the branched algorithm (ImportError, empty text, encrypted PDF, all-readers-fail) and the grounding-comment audit.

Common equations used in manufacturing reflow machines include the max ramp is max(s_i) over the region, where s_i = (T_i - T_{i-1}) / (t_i - t_{i-1}) for dt > 0. For the temperature band region, only consider segments where both endpoints satisfy tmin <= T <= tmax. For the zone band region, only consider zone_id in zones. For time band region, only consider t_start_s <= time_s <= t_end_s. For wetting/TAL-type metrics, compute time above a threshold `thr` using segment interpolation. For each TC, peak_tc = max(temp_c). min_peak_run = min(peak_tc), and required_peak = liquidus + peak_margin. Given heated length L_eff_cm, minimum dwell t_min_s, speed_max_cm_min = (L_eff_cm / t_min_s) * 60. Given L_eff_cm, maximum time t_max_s, speed_min_cm_min = (L_eff_cm / t_max_s) * 60.

TAL interpretation. "Time above liquidus / melting point" has two defensible readings — integral (sum of every above-threshold segment, including after cooling discontinuities) and contiguous (first upward crossing to last downward crossing, one window per run). Pick the reading the handbook endorses; if the integral reading causes > 80 % of runs to fall outside the handbook's TAL window, treat that as a signal to re-check the interpretation AND to confirm the window itself is handbook-grounded (not a memory-prior) before letting the verdict cascade into downstream ranking.

Representative-TC selection (per metric, not per run). Different metrics have different governing worst-case channels; the handbook naming a location (e.g. `largest_mass`) governs only the metric whose physical worst case matches that location. Default direction per metric: **ramp → fastest-heating** TC (exposed / smallest-mass); **peak** (minimum peak above liquidus) → **coolest-at-peak** TC (largest-mass / cold spot); **TAL** → compute per-TC and apply the handbook's upper bound to max-TAL and lower bound to min-TAL. Consistency of `tc_id` across ramp/TAL/peak is NOT a goal — only enforce one TC across all metrics when the handbook explicitly says so. Before writing any reducer, for each per-run question write a one-line comment stating what "worst case" means physically AND quoting the handbook sentence that names the location (if any). **Classify the quoted sentence before using it:** a *noun phrase listing placements* ("thermocouple a lead on the largest and smallest device", "probes on exposed and shielded locations") is **setup prose** — it tells the operator where to place probes, NOT which TC governs a metric; leave `cfg["<metric>_rep_location"] = None` and fall back to generic per-TC max/min. Only a sentence with an *imperative verb pointing at one metric and one location* ("use the coldest TC for peak", "the ramp limit applies to the fastest-heating thermocouple") is **reducer prose** and licenses setting `cfg["<metric>_rep_location"]`. Do NOT invent a per-metric placement from memory even if directionally plausible. **When the pre-ship anomaly scan reports any metric with `< 10 %` or `> 80 %` violators, trial at least two additional TC-selection policies (single consistent channel; per-metric physical worst case; run-level max/min/mean) and compare distributions before shipping — a cursory arithmetic spot-check on the already-chosen policy is tautological.** See `../references/representative-tc-selection.md` for the setup-vs-reducer classifier, worked examples, and the trial-alternative-policies branched algorithm.

Conveyor feasibility (no fabrication). The grounded templates `(L_eff_cm / t_min_s) * 60` and `(L_eff_cm / t_max_s) * 60` are the only sanctioned formulas. When `oven_model` is not directly mapped in the handbook, derive `L_eff_cm` from zone count × zone length (the leading digit prefix in oven_model names the zone count, e.g. `8Z`, `10Z`). Every input to the chosen formula (`L_eff_cm`, `t_min_s`, `t_max_s`, `zone_length_cm`, any `loading_factor`) must have an adjacent code comment quoting the handbook sentence that defines it; if any input is ungrounded, emit `required_min_speed_cm_min = null` and `meets = false` — never ship a self-admitted "suspicious" formula and never fabricate a parameter from memory. **PDF OCR routinely drops or misreads arithmetic operators (`×`, `÷`, parentheses); after translating any handbook formula to code, instantiate with sample values and verify units reduce to the expected output (`cm/min` for `required_min_speed_cm_min`). If the computed magnitude is implausibly tiny or huge (every run clears or every run fails trivially), swap the arrangement of each dimensionless parameter (divisor ↔ multiplier) and compare before shipping.** See `../references/conveyor-feasibility.md`.

"Best run" questions. The prompt wording decides the policy. **Strict scope** (prompt says "compliant", "meets all specs"): rank only runs where `ramp_ok AND tal_ok AND peak_ok AND feasibility_ok`; emit `null` for groups with no compliant run. **Soft scope** (prompt says "quality and efficiency", "recommended", unqualified "best"): rank ALL runs in the group by a composite score (yield desc, throughput desc, compliance-violation-count asc as tie-break/penalty, `run_id` asc); only emit `null` when the group has zero runs at all. A per-group sanity log reading `0/N compliant` is a stop signal — re-read the prompt and pick the mode before shipping. See `../references/best-run-ranking.md`.


Here are reference codes.
```python
# Build cfg from handbook text (see ../references/handbook-retrieval.md).
# Each value is accompanied by a comment with the verbatim handbook sentence.
# If no sentence can be quoted, the value is None and the metric emits null.
cfg = {
    # Handbook §X.Y: "<verbatim preheat region sentence>"
    # Shape: {"type":"temp_band", "tmin":..., "tmax":...}
    #     or {"type":"zone_band", "zones":[...]}
    #     or {"type":"time_band", "t_start_s":..., "t_end_s":...}
    "preheat_region": None,
    # Handbook §X.Y: "<verbatim ramp-limit sentence>"
    "ramp_limit_c_per_s": None,
    "tal_threshold_c_source": "solder_liquidus_c",   # if MES provides it
    # Handbook §X.Y: "<verbatim TAL lower bound sentence>"
    "tal_min_s": None,
    # Handbook §X.Y: "<verbatim TAL upper bound sentence>"
    "tal_max_s": None,
    # Handbook §X.Y: "<verbatim peak-margin sentence>"
    "peak_margin_c": None,
    # Per-metric representative-TC locations — independent, each may be None.
    # Only a REDUCER sentence (imperative verb + one metric + one location)
    # licenses a value here; SETUP prose (noun list of placements) does NOT.
    "ramp_rep_location": None,
    "peak_rep_location": None,
    "tal_rep_location":  None,
    # Conveyor feasibility rule-object; see ../references/conveyor-feasibility.md
    "conveyor_rule": None,
    "_handbook_status": None,   # "ok" or "unreadable"
}
runs = pd.read_csv(os.path.join(DATA_DIR, "mes_log.csv"))
tc   = pd.read_csv(os.path.join(DATA_DIR, "thermocouples.csv"))

runs["run_id"] = runs["run_id"].astype(str)
tc["run_id"]   = tc["run_id"].astype(str)
tc["tc_id"]    = tc["tc_id"].astype(str)

runs = runs.sort_values(["run_id"], kind="mergesort")
tc   = tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")
```

```python
#Always sort samples by time before any computation in thermocouple computation. Ignore segments where `dt <= 0`
df_tc = df_tc.sort_values(["run_id","tc_id","time_s"], kind="mergesort")
```

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
        if y0 > thr and y1 > thr:
            total += (t1 - t0)
            continue
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

Pre-ship checks. In addition to mechanical checks (string IDs, sorted arrays, 2dp, no NaN), run five semantic checks in this order:
(1) **Threshold-grounding check (precedes everything else).** For every numeric threshold used in a verdict (`ramp_limit_c_per_s`, `tal_min_s`, `tal_max_s`, `peak_margin_c`, `preheat_region`, feasibility `t_min_s`/`t_max_s`/`L_eff_cm`/`loading_factor`), confirm there is an adjacent code comment quoting the handbook sentence that defines it. If any threshold is a bare number with no quote, that threshold is ungrounded — set it to `None` and change the per-metric output to `null`. On ANY mass-fail (> 80 %) or near-zero (< 10 %) signal below, re-run this check *first* on the specific threshold driving the verdict: if the threshold is ungrounded, the threshold is the suspect, not the TC-selection rule or TAL interpretation. Do NOT branch into (3) or (4) until (1) is clean.
(2) **Hedge scan — class, not phrase list.** Match any phrase in three classes: (a) outside-expectation adjectives (synonym family of "suspicious": "surprising", "unusual", "unusually extreme", "unexpected", "weird", "strange", "odd", "off", "implausible"); (b) hedging modals / memory-prior substitutions ("probably", "I'll assume", "I think", "typical reflow is …", "the standard limit is …"); (c) rationalisations that explain away an anomaly ("real production anomaly", "systemic production pattern", "the data is just unusual", "that's just how reflow works", "genuine over-cooked profiles"). A near-synonym from (a) counts even if the exact word differs. Any match → re-open the handbook, re-run the policy decision.
(3) **Mechanical quantitative-anomaly scan — no judgement call.** Immediately after per-run verdicts are computed, emit a one-line summary of violator counts, e.g. `Q1: X/N, Q2: Y/N, Q3: Z/N violators`. If any count is `< 0.10 * N` or `> 0.80 * N`, the scan has fired — first re-run (1) on the driving threshold, then proceed to (4).
(4) **Paired quantitative-anomaly scan.** When two metrics share a selection rule (same TC-selection, same interpretation) and show *asymmetric* flag rates (one < 10 %, the other > 80 %), the shared rule is miscalibrated per metric, not the data. Hard stop: trial alternative TC-selection policies per `../references/representative-tc-selection.md` before shipping. Prerequisite: (1) is clean for both thresholds.
(5) **Per-question spot-check must compare against an alternative interpretation.** An arithmetic re-check of the already-chosen policy is tautological. For each question type, re-compute the same representative cell under at least ONE alternative interpretation (different TC-selection policy for Q1/Q2/Q3; integral vs. contiguous for TAL; divisor vs. multiplier arrangement for feasibility) and compare. If the two outputs differ dramatically (e.g. 5/N vs. 51/N violators), the policy is driving the verdict and must be re-examined before shipping. For "best run" picks, verify compliance (strict) or non-null emission (graded) per section 7.
