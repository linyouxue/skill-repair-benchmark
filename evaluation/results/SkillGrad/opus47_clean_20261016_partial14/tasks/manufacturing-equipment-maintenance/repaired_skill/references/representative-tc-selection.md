# Representative-TC selection (per-metric worst case)

Use this reference when the handbook mentions thermocouple placement by name
(e.g. `largest_mass`, "coldest point", "worst-case location", "fastest-heating
point") OR when the task prompt asks for the "representative" / "most
representative" thermocouple value. Skip when the handbook makes no placement
statement anywhere and the task asks only for an unqualified min/max.

## Why this matters

The handbook sometimes names a TC *location* (e.g. "measure the largest and
the smallest device") but does **not** necessarily designate that single
location as the governing representative for every metric. Each metric
(ramp, TAL, peak) has a different physical worst-case direction:

| Metric | Governing worst case | Typical TC location |
|--------|---------------------|---------------------|
| Ramp (upper limit) | fastest-heating channel | exposed / smallest-mass |
| Peak — minimum peak above liquidus | coolest-at-peak channel | largest-mass / cold spot |
| TAL — upper bound (overshoot) | hottest / longest-above-liquidus | exposed / smallest-mass |
| TAL — lower bound (minimum dwell) | coolest channel | largest-mass |

Four symmetric failure modes have occurred across iterations — all share one
root mechanism (the handbook contains placement language syntactically close
to a reducer policy; the agent locks on the first mapping that compiles; no
alternative TC-selection policy is trialled):

- **Under-use of handbook (iter_0):** generic `max`/`min` across all TCs
  while the handbook named a placement.
- **Over-use of handbook (iter_2):** one named placement applied uniformly
  to ramp, TAL, and peak.
- **Fabricated per-metric rule (iter_3):** per-metric placement invented
  from memory with no handbook quote.
- **Setup-prose misread as reducer prose (iter_4):** the handbook sentence
  "may be measured by thermocoupling a lead on the largest and smallest
  device" (a *measurement-setup* instruction) was read as a *per-metric
  reducer policy*, producing smallest_mass for ramp + largest_mass for
  TAL/peak. Resulted in 51/60 TAL non-compliance and 13/60 peak failures;
  the agent flagged the numbers as "unusually extreme" and shipped after a
  cursory per-TC arithmetic spot check.

**Consistency across questions is NOT required.** The handbook naming one
location for one metric does not license using it for all metrics.

## Setup prose vs. reducer prose — classifier

Before mapping any handbook sentence to `cfg["<metric>_rep_location"]`,
classify it. Only *reducer prose* licenses setting a per-metric location.

### Setup prose — a noun phrase listing placements

Tells the operator where to physically place probes during a thermal survey.
Does **not** designate any single TC as the per-metric representative.

Signatures:
- lists multiple locations without pointing at a single metric;
- verbs like "measured by", "placed at", "attached to", "thermocoupling a
  lead on" (describing the *setup act*, not a per-metric reduction);
- the surrounding paragraph is a *survey / measurement* paragraph, not a
  *compliance / verdict* paragraph.

Worked examples:
- *"non-uniformity from thermal mass differential may be measured by
  thermocoupling a lead on the largest and smallest device"* → setup prose.
  Six channels exist because probes were placed at various mass positions;
  downstream reducers still pick the per-metric physical worst case. Do NOT
  infer `peak_rep_location = largest_mass` or `ramp_rep_location =
  smallest_mass` from this sentence.
- *"thermocouples shall be placed on exposed and shielded locations
  throughout the thermal profile"* → setup prose.
- *"the oven survey uses probes at both the coldest and hottest points of
  the fixture"* → setup prose.

Action: leave `cfg["<metric>_rep_location"] = None`; fall back to generic
per-TC max/min reduction via the per-metric worst-case table above.

### Reducer prose — imperative verb + one metric + one location

Explicitly designates one TC as the representative for one specific metric.

Signatures:
- imperative verb ("use", "report", "evaluate", "apply", "report from");
- names ONE metric (ramp / TAL / peak / dwell);
- names ONE location.

Worked examples:
- *"use the coldest TC for the peak check"* → reducer prose for peak;
  licenses `peak_rep_location = "coldest_point"` (or equivalent).
- *"the ramp-rate limit applies to the fastest-heating thermocouple"* →
  reducer prose for ramp; licenses `ramp_rep_location = "smallest_mass"`
  (or the handbook's named fast-heating location).
- *"TAL is reported from the largest-mass sensor"* → reducer prose for TAL
  lower bound.

Action: set `cfg["<metric>_rep_location"] = <location>` for that one metric
only; the other `*_rep_location` keys stay `None` unless they too have a
reducer sentence.

### Classifier shortcut

If the quoted sentence contains the word *and* joining two locations
(`"<loc A> and <loc B>"`), it is almost certainly setup prose — a single
reducer sentence names a single governing TC, not a pair.

## Pre-coding enumeration

For each per-run question, write a comment stating:

1. What does "worst case" mean physically for this metric? (fastest-heating,
   hottest-above-liquidus, coolest-at-peak, longest-above-liquidus, …)
2. Which TC location satisfies it according to the handbook text?
3. Is the quoted handbook sentence *reducer prose* (imperative + one metric +
   one location) or *setup prose* (noun list of placements)? If setup, the
   location is `None` for this metric and generic fallback applies.

Only after this enumeration, write the reducer.

## Decision procedure (per metric)

### Ramp (upper-limit question)

- **Branch A — handbook has a REDUCER sentence naming a fast-heating /
  exposed / smallest-mass location AND it exists in the TC data.** Filter
  to that location; max ramp across matching TCs; tie-break `tc_id` asc.
- **Branch B — handbook has only SETUP prose, or names only a cool / large-
  mass location.** Generic fallback: max ramp per TC across all TCs,
  `(max_value, smallest_tc_id)`. Do NOT use a cool-location placement for
  ramp.
- **Branch C — handbook offers no placement statement at all.** Generic
  fallback as in Branch B.

### Peak (minimum-peak-above-liquidus question)

- **Branch A — handbook has a REDUCER sentence naming a cool / largest-mass
  / cold-spot location.** Filter to that location; max temp per matching
  TC; min across those TCs (coolest-at-peak); tie-break `tc_id` asc.
- **Branch B — handbook has only SETUP prose, or names only a fast-heating
  location.** Generic fallback: `(min peak_tc, smallest_tc_id)` across all
  TCs.

### TAL (window with upper and/or lower bound)

- Compute TAL **per TC** first — do not collapse to a single TC up front.
- Apply each bound to its governing channel:
  - Upper (overshoot) bound → max TAL across TCs (`tal_upper = max`).
  - Lower (minimum-dwell) bound → min TAL across TCs (`tal_lower = min`).
- A single-TC collapse for TAL is only correct when the handbook has
  REDUCER prose explicitly naming one TC for TAL.

## Trial alternative TC-selection policies before shipping

**When the pre-ship mechanical anomaly scan reports any metric with `< 10 %`
or `> 80 %` violators, do NOT ship on the first interpretation.** An
arithmetic re-check of the already-chosen policy only verifies computation,
not interpretation — it is tautological against the policy that produced the
anomaly. Re-compute Q1/Q2/Q3 violator counts under at least two additional
policies and compare distributions.

Three plausible policies to trial (plus whatever the first attempt was):

| Policy | Ramp | TAL | Peak |
|---|---|---|---|
| α — single consistent channel | handbook-named | handbook-named | handbook-named |
| β — per-metric physical worst case | fastest-heating | max/min TAL across TCs | coolest-at-peak |
| γ — run-level reduction (no filter) | max across all TCs | max/min TAL across all TCs | min across all TCs |

Code:

```python
import pandas as pd

def violator_counts(df_tc, runs, policy: str, cfg: dict,
                    max_slope_fn, tal_fn) -> dict:
    """Return (q1_viol, q2_viol, q3_viol) under one policy label."""
    q1 = q2 = q3 = 0
    for run_id, run in runs.iterrows():
        tc_run = df_tc[df_tc["run_id"] == run["run_id"]]
        # ramp
        if policy == "alpha":
            pool_ramp = tc_run[tc_run["location"] == cfg["ramp_rep_location"]]
        elif policy == "beta":
            pool_ramp = tc_run[tc_run["location"] == "smallest_mass"] \
                        if "smallest_mass" in tc_run["location"].values \
                        else tc_run
        else:  # gamma
            pool_ramp = tc_run
        ramps = [max_slope_fn(g) for _, g in pool_ramp.groupby("tc_id")]
        ramps = [r for r in ramps if r is not None]
        if ramps and max(ramps) > cfg["ramp_limit_c_per_s"]:
            q1 += 1
        # peak and tal — analogous branches, policy-indexed
        # ...
    return {"q1": q1, "q2": q2, "q3": q3}

def choose_policy(df_tc, runs, cfg, max_slope_fn, tal_fn,
                  N: int) -> str:
    """Pick the policy whose violator distribution is most plausible."""
    results = {p: violator_counts(df_tc, runs, p, cfg, max_slope_fn, tal_fn)
               for p in ("alpha", "beta", "gamma")}
    # plausibility: 5–30 % non-compliance per metric is a healthy band
    def plausible(d):
        return all(0.05 * N <= v <= 0.30 * N for v in d.values())
    plausible_policies = [p for p, d in results.items() if plausible(d)]
    if len(plausible_policies) == 1:
        return plausible_policies[0]
    # tie-break: prefer the policy whose placement is backed by REDUCER prose
    # (classifier above); otherwise prefer beta (physical worst case).
    return plausible_policies[0] if plausible_policies else "beta"
```

## Code (per-metric reducers)

```python
import pandas as pd

def ramp_representative(tc_rows: pd.DataFrame, cfg: dict, max_slope_fn) -> tuple:
    """Fastest-heating TC governs. tc_rows: all TCs for one run."""
    fast_loc = cfg.get("ramp_rep_location")   # only set if REDUCER prose
    pool = tc_rows
    if fast_loc is not None:
        matched = tc_rows[tc_rows["location"] == fast_loc]
        if not matched.empty:
            pool = matched
    per_tc = []
    for tc_id, grp in pool.groupby("tc_id"):
        s = max_slope_fn(grp)
        if s is not None:
            per_tc.append((s, tc_id))
    if not per_tc:
        return (None, None)
    per_tc.sort(key=lambda x: (-x[0], x[1]))      # max value, smallest tc_id
    return per_tc[0]

def peak_representative(tc_rows: pd.DataFrame, cfg: dict) -> tuple:
    """Coolest-at-peak TC governs."""
    cool_loc = cfg.get("peak_rep_location")       # only set if REDUCER prose
    pool = tc_rows
    if cool_loc is not None:
        matched = tc_rows[tc_rows["location"] == cool_loc]
        if not matched.empty:
            pool = matched
    per_tc = [(grp["temp_c"].max(), tc_id) for tc_id, grp in pool.groupby("tc_id")]
    per_tc.sort(key=lambda x: (x[0], x[1]))       # min value, smallest tc_id
    return per_tc[0] if per_tc else (None, None)

def tal_window_representatives(tc_rows: pd.DataFrame, thr: float, tal_fn) -> dict:
    """Compute TAL per TC; return both upper- and lower-bound governing values."""
    per_tc = [(tal_fn(grp, thr), tc_id) for tc_id, grp in tc_rows.groupby("tc_id")]
    per_tc = [(v, t) for (v, t) in per_tc if v is not None]
    if not per_tc:
        return {"tal_upper": (None, None), "tal_lower": (None, None)}
    per_tc.sort(key=lambda x: (-x[0], x[1])); upper = per_tc[0]
    per_tc.sort(key=lambda x: (x[0],  x[1])); lower = per_tc[0]
    return {"tal_upper": upper, "tal_lower": lower}
```

## Verification

Four post-reduction checks:

```python
# 1. Setup-vs-reducer classifier check — for every non-None rep_location,
#    confirm the quoted handbook sentence is REDUCER prose, not SETUP prose.
for key in ("ramp_rep_location", "peak_rep_location", "tal_rep_location"):
    if cfg.get(key) is not None:
        quote = cfg_quotes.get(key, "")
        # setup-prose heuristic: lists two locations joined by "and" without
        # an imperative verb for this metric
        has_imperative = any(v in quote.lower()
                             for v in ("use ", "report", "apply", "evaluate",
                                       "the ... check", "is reported from"))
        has_metric_name = any(m in quote.lower()
                              for m in ("ramp", "tal", "peak", "dwell",
                                        "liquidus")) and key.split("_")[0] in quote.lower()
        if not (has_imperative and has_metric_name):
            raise AssertionError(
                f"cfg[{key}]={cfg[key]!r} is backed by SETUP prose "
                f"({quote!r}), not REDUCER prose. Set to None and fall "
                f"back to generic per-TC reduction for this metric."
            )

# 2. Per-metric paired-anomaly check (the strongest signal that one TC was
#    applied uniformly across metrics with different physical worst cases,
#    OR that a setup-prose sentence was misread as per-metric reducer).
n = len(runs)
rates = {}
for metric in ("ramp", "tal", "peak"):
    viol = sum(not r[f"{metric}_ok"] for r in runs)
    rates[metric] = viol / n
near_zero = [k for k, v in rates.items() if v < 0.10]
mass_fail = [k for k, v in rates.items() if v > 0.80]
if near_zero and mass_fail:
    raise AssertionError(
        f"paired anomaly: {near_zero} < 10% violators alongside {mass_fail} "
        f">80% violators — the shared TC-selection rule is miscalibrated per "
        f"metric. Trial alternative policies (alpha/beta/gamma above) "
        f"before shipping."
    )

# 3. Trial-alternative-policies audit when any metric is anomalous.
if any(v < 0.10 or v > 0.80 for v in rates.values()):
    trial_results = {p: violator_counts(df_tc, runs, p, cfg, max_slope_fn, tal_fn)
                     for p in ("alpha", "beta", "gamma")}
    print("trial policies:", trial_results)
    assert any(all(0.05*n <= cnt <= 0.30*n for cnt in d.values())
               for d in trial_results.values()), (
        "no alternative policy produced a plausible distribution — "
        "re-check thresholds (grounding), then re-read handbook for "
        "reducer prose on each metric."
    )

# 4. Consistency assertion only in the handbook-single-TC branch.
if cfg.get("single_tc_for_all_metrics_handbook_stated"):
    tc_ids = {ramp_tc_id, peak_tc_id, tal_upper_tc_id, tal_lower_tc_id} - {None}
    assert len(tc_ids) <= 1, f"handbook names one TC but got {tc_ids}"
```

**If check 1 fires:** the per-metric `rep_location` is backed by setup prose,
not reducer prose. Set it to `None`, re-run the reducer with generic fallback,
and re-compute the per-run verdict before shipping.

**If check 2 fires:** the shared TC-selection rule is the suspect, not the
data. Re-enumerate "worst case" per metric and re-run the reducers under at
least two alternative policies (check 3).

**If check 3 fires with no plausible alternative:** the thresholds are the
next suspect — re-run the handbook-grounding check (`handbook-retrieval.md`
verification) on the specific threshold driving each anomalous metric.

**If check 4 fires (handbook-single-TC branch only):** branch A was skipped
for at least one metric. Re-run that metric through the filter.
