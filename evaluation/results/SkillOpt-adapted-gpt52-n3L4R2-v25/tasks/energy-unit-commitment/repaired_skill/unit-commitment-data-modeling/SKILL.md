---
name: unit-commitment-data-modeling
description: Use for parsing structured unit commitment input data from JSON, CSV, benchmark cases, spreadsheets, databases, or nested tables; finding fields for time periods, resources, load, reserve, generator limits, initial conditions, startup data, renewable availability, and production costs without assuming one source-specific schema.
---

# Unit Commitment Structured Data Parsing

Use this skill when a unit commitment task provides structured data and you need to map fields into UC concepts. The source may be JSON, CSV, spreadsheets, database tables, or nested dictionaries. The prompt and schema are the source of truth; do not assume one benchmark or package.

## Parsing Workflow

1. Load the source with a structured parser and retain the raw object unchanged; for `/root/network.json`, inspect the complete recursively nested schema rather than probing only expected keys.
2. Build a schema inventory containing every top-level and nested field, its resource/time scope, shape, units, source path, and whether it is required, optional, or inapplicable. Do not proceed while any field is unclassified.
3. Identify the authoritative time axis, period duration, labels, and source order. For the task case, require exactly 48 periods, preserve their order, use internal indices `0..47`, and map report labels separately to hours `1..48`.
4. Identify explicit thermal and renewable resource sets, preserving exact names, source order, and one-to-one identity. Reject duplicate names, ambiguous classification, dropped records, or records assigned to both sets.
5. Map every applicable input field into a typed scalar, ordered vector, matrix, or curve table with explicit dimensions and units. Preserve source values; do not silently default, aggregate, rescale, round, or reorder them.
6. Normalize system demand and spinning reserve as total system-wide arrays, and normalize resource-specific availability, limits, initial conditions, startup tiers, and production-cost curves without changing their scope.
7. Run the strict parser gate and mapping audit before creating model variables. Any missing, ambiguous, duplicated, nonfinite, unit-inconsistent, or incorrectly sized required value must raise an error identifying its source path and expected shape.

## Map Concepts, Not Names

Different sources use different names. Map by meaning, units, shape, and context.

| UC concept | Look for |
| --- | --- |
| Horizon | periods, hours, timestamps, interval count |
| Demand | load, system demand, net load, zone load |
| Reserve requirement | spinning, operating, contingency, regulation reserve |
| Resource sets | thermal, renewable, storage, import/export |
| Commitment status | on/off, online, active, unit status |
| Output limits | minimum stable output, maximum output, availability |
| Ramping | ramp up/down, startup capability, shutdown capability |
| Minimum up/down | required duration after start/stop |
| Initial conditions | initial status, initial output, time already on/off |
| Must-run | forced online, fixed status |
| Startup data | fixed costs or tiers by prior offline duration |
| Production cost | linear coefficients, heat rate, piecewise or total-cost curves |
| Renewable availability | hourly min/max output or forecast bounds |

## Common Data Shapes

- **Scalar by resource:** min up/down, ramp rates, startup ramp, must-run.
- **Time series by system/zone:** demand and reserve requirement.
- **Time series by resource:** renewable availability or outage status.
- **Curve/tier tables:** startup costs and production-cost breakpoints.
- **Nested resource objects:** generator-specific limits, status, and costs.

Normalize into a small representation:

```python
case = {
    "periods": periods,                  # length T
    "thermal_names": thermal_names,      # length G, source order
    "renewable_names": renewable_names,  # length R, source order
    "demand": demand,                    # shape (T,)
    "reserve_requirement": reserve,       # shape (T,)
    "thermal": thermal_params,
    "renewable_min": renewable_min,       # shape (R, T)
    "renewable_max": renewable_max,       # shape (R, T)
}
```

## Time, Ordering, And Units



### Strict `/root/network.json` normalization gate

Before modeling, materialize a manifest for the complete input: source path, exact field path, semantic concept, scope, units, shape, and destination in the normalized case. The manifest must cover total demand, total spinning reserve, thermal and renewable identities, Pmin/Pmax, renewable availability, ramp-up/ramp-down and startup/shutdown limits, minimum up/down times, must-run flags, initial status, initial output where supplied, elapsed initial on/off duration, startup/shutdown data, startup tiers with offline-duration thresholds, and every production-cost breakpoint or coefficient. Require all applicable time series to have length 48 and all resource vectors to match the preserved source resource order. Verify finite numeric values, valid bounds, nonnegative durations where applicable, compatible power/ramp/cost units, unique curve points and tier thresholds, and consistency between initial status and elapsed duration. Reject missing, ambiguous, duplicated, nonfinite, unit-inconsistent, or incorrectly sized fields; never infer a default from absence. Keep total thermal production distinct from output above minimum and record the single conversion used by the model and report. The gate passes only when every applicable source field has exactly one normalized destination and every normalized field has a recorded source path.

- Use the input horizon as authoritative.
- Preserve source period order.
- Keep zero-based internal indexes separate from one-based/timestamped report labels.
- Verify every time-series length equals `T`.
- Preserve resource order unless the prompt requires sorting.
- Treat resource IDs as opaque strings.
- Keep thermal and renewable sets separate when constraints differ.
- Check power units, period duration, ramp-rate units, and cost units before converting anything.

Basic checks:

```python
assert len(demand) == T
assert len(reserve_requirement) == T
for r in renewable_resources:
    assert len(r["min"]) == T
    assert len(r["max"]) == T
```

## Production Convention

Many UC models use output above minimum internally, while reports often require actual MW.

```python
actual_output = pmin * commitment + output_above_min
output_above_min = actual_output - pmin * commitment
```

Pick one internal convention and convert carefully for reporting, ramping, reserve deliverability, and cost.

## Startup Tiers

Startup tiers are usually keyed by prior offline duration. Parse thresholds and costs without assuming order.

```python
def choose_startup_tier(tiers, prior_offline_duration):
    tiers = sorted(tiers, key=lambda x: x["lag"])
    chosen = tiers[0]
    for tier in tiers:
        if tier["lag"] <= prior_offline_duration:
            chosen = tier
        else:
            break
    return chosen
```

Keep prior offline duration consistent with initial status and transition timing.

## Cost Curves

Identify whether points are total cost, marginal cost, incremental segment cost, or heat-rate data. For total-cost breakpoints:

```python
def interpolate_total_cost(points, output_mw):
    pts = sorted((float(p["mw"]), float(p["cost"])) for p in points)
    if output_mw <= pts[0][0]:
        return pts[0][1]
    if output_mw >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= output_mw <= x1:
            a = (output_mw - x0) / (x1 - x0)
            return y0 + a * (y1 - y0)
    raise ValueError("output outside cost curve")
```

If the first point is at minimum output, it may represent online minimum-output cost. Do not invent additional no-load or shutdown costs unless provided.

## Renewables

- Parse hourly minimum and maximum output.
- If min equals max, output is fixed in that period.
- If curtailment is allowed, output can be anywhere between min and max.
- Do not count renewable headroom as spinning reserve unless explicitly allowed.
- Renewable cost is zero unless the task/data says otherwise.

## Parser-Level Validation

Before solving, check:

```python
assert np.all(np.isfinite(demand))
assert np.all(np.isfinite(reserve_requirement))
assert np.all(thermal_pmin <= thermal_pmax)
assert np.all(renewable_min <= renewable_max)
assert all(len(curve) >= 2 for curve in production_curves.values())
assert all(len(tiers) >= 1 for tiers in startup_tiers.values())
```

Also check missing required fields, duplicate IDs, mismatched lengths, negative impossible limits, repeated cost points, nonmonotone startup lags, and inconsistent initial status/output.

## Common Mistakes



## Mapping Audit Before Model Construction

Emit and inspect a field-coverage audit before building variables. For each source field, report its exact path, semantic interpretation, units, scope (system, resource, or period), normalized destination, shape, and whether it is used in constraints, objective, extraction, or report validation. Require zero unmapped applicable fields and zero normalized fields without a source path. Separately reconcile the ordered thermal and renewable name lists, the 48 source periods, demand and reserve totals, all resource time series, initial-condition records, startup tiers, and cost curves. Treat a failed reconciliation as fatal; a schedule must not be generated from a partially mapped case.

- Hard-coding a familiar schema instead of inspecting the data.
- Losing ordering when converting dictionaries or tables into arrays.
- Joining tables on the wrong key or duplicating resources.
- Confusing total output with output above minimum.
- Confusing reserve, capacity, availability, and dispatch.
- Treating every cost curve as marginal cost.
- Ignoring startup tier lags or initial offline duration.
- Assuming renewable maximum output must always be used.
