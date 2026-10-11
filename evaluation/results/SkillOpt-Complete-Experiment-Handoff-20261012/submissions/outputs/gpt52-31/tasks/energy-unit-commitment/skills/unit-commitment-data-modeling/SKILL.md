---
name: unit-commitment-data-modeling
description: Use for parsing structured unit commitment input data from JSON, CSV, benchmark cases, spreadsheets, databases, or nested tables; finding fields for time periods, resources, load, reserve, generator limits, initial conditions, startup data, renewable availability, and production costs without assuming one source-specific schema.
---

# Unit Commitment Structured Data Parsing

Use this skill when a unit commitment task provides structured data and you need to map fields into UC concepts. The source may be JSON, CSV, spreadsheets, database tables, or nested dictionaries. The prompt and schema are the source of truth; do not assume one benchmark or package.

## Parsing Workflow

1. Load data with structured parsers: JSON as objects, CSV/sheets as tables, databases as query results.
2. Inspect schema: top-level keys, tables/sheets, resource groups, time-series fields, cost curves, startup tiers, and initial-condition fields.
3. Identify the time axis: number of periods, labels, duration, and report convention.
4. Identify resource sets: thermal, renewable, storage, imports, zones, reserve products, or network objects.
5. Normalize fields into arrays/tables with explicit shapes.
6. Preserve original names and source ordering for final reports.
7. Run parser-level checks before modeling.



### network.json Schema Discovery Playbook

For unknown UC JSON schemas, inspect structure before mapping fields:

```python
with open("network.json") as f:
    data = json.load(f)

print(data.keys())
```

Then enumerate likely UC containers:

```python
for k, v in data.items():
    print(k, type(v), getattr(v, "__len__", lambda: "na")())
```

Look for:

- generator/resource collections (`generators`, `units`, `thermal`, `renewables`, `resources`)
- time-series containers (`time_series`, `profiles`, `load`, `demand`, `reserve`)
- horizon metadata (`T`, `periods`, `hours`, timestamps)
- nested cost/startup structures (`cost_curve`, `piecewise`, `startup`, `segments`)
- initial-condition fields (`initial_status`, `initial_output`, `time_on`, `time_off`)

Do not assume one benchmark schema or fixed nesting depth. Infer meaning from shape, units, and neighboring fields.

Determine the horizon `T` from authoritative time-series length or explicit metadata and verify every hourly series matches it exactly. Common silent failures are off-by-one indexing errors and treating 1-based report hours as 0-based internal indexes.

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



Use deterministic array normalization with explicit dimensions:

```python
thermal_names = []
renewable_names = []
thermal_pmin = []      # shape (G,)
thermal_pmax = []      # shape (G,)
renewable_max = []     # shape (R, T)
```

Preserve generator names verbatim and preserve source iteration order when building arrays and reports. Never sort IDs unless the task explicitly requests it.

For every normalized array, document intended shape:

- generator scalars: `(G,)`
- hourly system series: `(T,)`
- generator-by-time data: `(G, T)` or `(R, T)`
- startup tiers: ragged per-generator lists
- production curves: ragged breakpoint lists

If the source uses dictionaries keyed by generator ID, materialize a stable ordered name list first, then build arrays consistently from that ordering.

## Time, Ordering, And Units

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



## Thermal vs Renewable Classification

Classify resources using multiple signals rather than a single field:

- explicit type/fuel/category labels (`thermal`, `renewable`, `wind`, `solar`, `gas`, `coal`)
- presence of commitment variables or UC fields (minimum up/down, startup cost, startup tiers)
- positive minimum stable output (`pmin > 0`)
- ramp-rate and reserve eligibility fields
- renewable availability profiles varying by hour

Fallback heuristic:

```python
is_thermal = (
    has_commitment_fields
    or has_startup_cost
    or has_min_up_down
    or pmin > 0
)
```

Do not classify solely from zero marginal cost or time-varying limits.

Extract system demand and spinning-reserve requirements as hourly arrays of shape `(T,)`. Reserve requirements are often stored separately from demand and may use names like `spin`, `operating_reserve`, or `contingency_reserve`.

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



Interpret initial conditions carefully because schemas differ:

- `initial_status` may encode binary on/off or signed time-in-state
- `time_on` / `time_off` are usually durations already spent online/offline before period 1
- `initial_output` is typically actual MW at time 0, not output above minimum
- negative signed status values often mean offline duration

Validate consistency:

```python
assert T > 0
assert len(demand) == T
assert len(reserve_requirement) == T
assert np.all(thermal_pmin >= 0)
assert np.all(thermal_pmax >= thermal_pmin)
assert np.all(ramp_up >= 0)
assert np.all(ramp_down >= 0)
```

For production costs, distinguish:

- linear marginal coefficients
- piecewise incremental segments
- total-cost breakpoints
- heat-rate curves

For startup data, preserve all startup tiers and offline-duration thresholds exactly as provided. Check that startup lags are monotone and that each generator has the required cost representation before building the UC model.

Also check missing required fields, duplicate IDs, mismatched lengths, negative impossible limits, repeated cost points, nonmonotone startup lags, and inconsistent initial status/output.

## Common Mistakes

- Hard-coding a familiar schema instead of inspecting the data.
- Losing ordering when converting dictionaries or tables into arrays.
- Joining tables on the wrong key or duplicating resources.
- Confusing total output with output above minimum.
- Confusing reserve, capacity, availability, and dispatch.
- Treating every cost curve as marginal cost.
- Ignoring startup tier lags or initial offline duration.
- Assuming renewable maximum output must always be used.
