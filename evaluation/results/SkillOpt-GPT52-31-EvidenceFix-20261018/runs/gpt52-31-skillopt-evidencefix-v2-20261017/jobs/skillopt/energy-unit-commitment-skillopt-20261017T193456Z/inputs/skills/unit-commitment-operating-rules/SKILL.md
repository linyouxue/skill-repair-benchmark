---
name: unit-commitment-operating-rules
description: Use for day-ahead or multi-period unit commitment problems, including thermal on/off schedules, dispatch, startup/shutdown logic, minimum up/down time, ramping, spinning reserve deliverability, renewable curtailment, operating-cost accounting, and independent feasibility checks for power-system operations schedules.
---

# Unit Commitment Operating Rules

Use this skill when a task asks for a day-ahead or multi-period unit commitment schedule with generators, load, reserves, operating constraints, and cost tradeoffs.

This is a reusable UC operating guide. It gives formulation and validation patterns, not a complete task-specific mathematical model.

## UC In One Paragraph

Unit commitment decides which generators are online over time, when they start or stop, how much they produce, and how much reserve they can physically provide. It is harder than hourly economic dispatch because startup/shutdown decisions, ramping, minimum up/down time, reserve deliverability, initial conditions, and cost curves couple one period to the next.

## Keep These Concepts Separate

For each thermal unit `g` and period `t`:

```python
u[g, t]      # commitment/on status, binary
start[g, t]  # startup transition, binary
stop[g, t]   # shutdown transition, binary
p[g, t]      # production variable: know whether actual MW or above-minimum MW
r[g, t]      # scheduled reserve
```

Reports often require actual MW output. Many UC models internally use output above minimum:

```python
actual_output = pmin[g] * u[g, t] + p_above_min[g, t]
p_above_min = actual_output - pmin[g] * u[g, t]
```

Do not mix these conventions in ramping, reserve, cost, or reporting.



Transition constraints are especially sensitive to this choice. If the exported report uses actual MW `P`, then:

```python
p_above_min[g, t] = P[g, t] - pmin[g] * u[g, t]
```

Any startup/shutdown derating, reserve deliverability, or above-minimum ramping rule must be applied to `p_above_min`, not directly to `P`, unless the data explicitly defines transition limits in actual MW.
## Core Feasibility Checks

Before reporting a schedule, independently verify:

- every resource appears exactly once and all time-series have length `T`;
- commitment, startup, and shutdown are binary;
- offline thermal units have zero production and zero reserve;
- online thermal units respect min/max output;
- must-run units are online when required;
- startup/shutdown indicators match commitment transitions;
- demand balance holds in every period;
- renewable output stays within period-specific bounds;
- scheduled reserve meets the system requirement;
- reserve is deliverable under headroom, startup/shutdown capability, and ramp limits;
- minimum up/down time and initial conditions are respected;
- cost and summary fields are recomputed from arrays.

## Transition Logic

Link startup/shutdown to commitment and the initial state:

```python
prev_u = initial_on[g] if t == 0 else u[g, t - 1]
u[g, t] - prev_u == start[g, t] - stop[g, t]
start[g, t] + stop[g, t] <= 1
```

Equivalent validation pattern:

```python
prev_on = initial_on[g]
for t in range(T):
    assert start[g, t] == int(u[g, t] == 1 and prev_on == 0)
    assert stop[g, t] == int(u[g, t] == 0 and prev_on == 1)
    prev_on = u[g, t]
```

## Capacity And Offline Zeroes

For actual-MW production:

```python
pmin[g] * u[g, t] <= production[g, t] <= pmax[g] * u[g, t]
0 <= reserve[g, t]
```

For above-minimum production:

```python
cap = pmax[g] - pmin[g]
0 <= p_above_min[g, t] <= cap * u[g, t]
0 <= reserve[g, t]
```

If `u[g, t] == 0`, both production and reserve must be zero.

## Demand, Renewables, And System Reserve

Use the task's system/zone/network convention. For a single-zone system:

```python
thermal_gen = sum(actual_thermal[g, t] for g in thermal_units)
renew_gen = sum(renewable_output[r, t] for r in renewable_units)
assert abs(thermal_gen + renew_gen - demand[t]) <= tol
assert sum(reserve[g, t] for g in thermal_units) >= reserve_requirement[t] - tol
```

Renewables:

```python
renewable_min[r, t] <= renewable_output[r, t] <= renewable_max[r, t]
```

If min equals max, output is fixed. If curtailment is allowed, output may be below max. Do not count renewable headroom as spinning reserve unless the prompt explicitly allows it.

## Reserve Deliverability

Reserve is not just unused nameplate capacity. Production and reserve compete for the same physical capability, and reserve must be deployable.

Headroom-only checks are too weak:

```python
# Not enough by itself:
reserve[g, t] <= pmax[g] - production[g, t]
reserve[g, t] <= ramp_up[g]
```

Use joint production-plus-reserve checks. With actual-MW production:

```python
production[g, t] + reserve[g, t] <= pmax[g] * u[g, t]
```

With above-minimum production:

```python
p_above_min[g, t] + reserve[g, t] <= (pmax[g] - pmin[g]) * u[g, t]
```

Startup capability can tighten the startup period. If `startup_limit` is maximum total output during startup:

```python
if start[g, t] == 1:
    production[g, t] + reserve[g, t] <= startup_limit[g]
```

A linear above-minimum pattern is:

```python
startup_reduction = max(pmax[g] - startup_limit[g], 0.0)
p_above_min[g, t] + reserve[g, t] <= (
    (pmax[g] - pmin[g]) * u[g, t]
    - startup_reduction * start[g, t]
)
```

Apply analogous shutdown-period or pre-shutdown capability rules when the data and prompt require them. A common symmetric formulation is:

```python
shutdown_reduction = max(pmax[g] - shutdown_limit[g], 0.0)

p_above_min[g, t] + reserve[g, t] <= (
    (pmax[g] - pmin[g]) * u[g, t]
    - startup_reduction * start[g, t]
    - shutdown_reduction * stop[g, t]
)
```

This is a joint capability constraint: energy and reserve together cannot exceed the derated transition capability. Do not schedule reserve assuming full headroom during startup or shutdown hours.

Verifier-style audit pattern:

```python
cap = pmax[g] - pmin[g]
p_above = production[g, t] - pmin[g] * u[g, t]
lhs = p_above + reserve[g, t]
rhs = (
    cap * u[g, t]
    - startup_reduction * start[g, t]
    - shutdown_reduction * stop[g, t]
)
assert lhs <= rhs + tol
```

## Ramping

Use initial output/status for the first period. When reserve must be deliverable, ramp-up usually applies to production plus reserve:

```python
previous = initial_above_min[g] if t == 0 else p_above_min[g, t - 1]
p_above_min[g, t] + reserve[g, t] - previous <= ramp_up[g]
previous - p_above_min[g, t] <= ramp_down[g]
```

If your model uses actual production, convert consistently before applying above-minimum ramp checks. Recheck ramping after any dispatch or repair step.



Be explicit about whether startup/shutdown ramp limits are defined on actual MW or above-minimum MW. A frequent error is validating ramping on actual output while validating reserve deliverability on above-minimum output, causing startup hours to appear feasible even though `p_above_min + reserve` exceeds startup capability.
## Minimum Up/Down Time

Minimum up/down constraints are time-window constraints triggered by starts/stops. Validation pattern:

```python
if start[g, t] == 1:
    for tau in range(t, min(T, t + min_up[g])):
        assert u[g, tau] == 1

if stop[g, t] == 1:
    for tau in range(t, min(T, t + min_down[g])):
        assert u[g, tau] == 0
```

Account for pre-horizon time already on/off. Follow the prompt on whether post-horizon obligations are enforced.

## Startup Costs

Startup cost may depend on prior offline duration. A common tier rule is largest lag not exceeding prior offline duration:

```python
def choose_startup_cost(tiers, offline_duration):
    tiers = sorted(tiers, key=lambda z: z["lag"])
    chosen = tiers[0]
    for tier in tiers:
        if tier["lag"] <= offline_duration:
            chosen = tier
        else:
            break
    return chosen["cost"]
```

Update offline duration from initial status and the commitment trajectory. Be careful: duration should describe time offline before the startup period.

## Production Costs



## Cost Modeling & Economic UC Sanity

Feasible but very expensive schedules usually come from cost-model inconsistencies (especially mixing actual-MW vs above-minimum conventions) or from reserve/commitment choices that ignore marginal costs. Use this section to ensure your UC objective matches the verifier’s accounting and your own report fields.

### 1) Define the MW convention used by the cost curve

Many instances provide piecewise **total-cost** points (\$/h) as a function of **actual output MW when online**. Others provide incremental/segment costs. You must map the schedule’s *actual* MW into the curve’s expected MW.

Let:
- `u[g,t] ∈ {0,1}`
- `P[g,t]` = **actual** MW output (what the report requires)
- `pmin[g], pmax[g]`
- `p_above[g,t] = P[g,t] - pmin[g]*u[g,t]` (≥0)

If you model dispatch above-minimum internally, always compute costs using the correct argument:

```text
P[g,t] = pmin[g]*u[g,t] + p_above[g,t]
```

### 2) Total cost decomposition (do not double count pmin)

For each unit and hour, total operating cost typically has these components (only include components that exist in data/prompt):

```text
TotalCost = Σ_t Σ_g [ NoLoadCost[g]*u[g,t]
                      + StartupCost[g,t]*start[g,t]
                      + ShutdownCost[g]*stop[g,t]
                      + VariableEnergyCost[g,t](P[g,t]) ]
```

Key rule to avoid pmin double counting:
- If `VariableEnergyCost(P)` is a **total-cost curve** that already includes the cost of producing at `pmin` when `P=pmin`, then **do not add** an additional `NoLoadCost` unless the data explicitly defines it separately.
- If variable costs are defined **only for energy above minimum** (e.g., segments in `p_above`), then you may need `NoLoadCost` (or a fixed cost at minimum) *if and only if* the dataset provides it.

### 3) Piecewise variable costs: use segments, not a single slope

If the data provides piecewise points for total cost `C(P)` (monotone increasing in `P`), compute hourly variable cost as:

```text
VariableEnergyCost[g,t] = C_g(P[g,t])    if u[g,t]=1
                        = 0             if u[g,t]=0
```

If the data provides piecewise **incremental** costs over segments (common in UC MILPs), model energy in segments so the marginal cost changes with output. Do not approximate with an average slope across the whole range.

### 4) Worked example: actual MW vs above-minimum and where each is used

Suppose a unit has `pmin=50`, `pmax=100`, `u=1`.
- If you decide `p_above=20`, then `P = 50 + 20 = 70 MW`.

Use these consistently:
- **Reporting**: report `P` (70 MW).
- **Capacity**: `50 ≤ P ≤ 100` (or `0 ≤ p_above ≤ 50`).
- **Reserve headroom** (deliverability): `P + R ≤ 100` (or `p_above + R ≤ 50`).
- **Ramping**: if ramps are defined on above-minimum, ramp on `p_above` (but ensure you convert correctly from initial actual output). If ramps are defined on actual output, ramp on `P`.
- **Costs**:
  - If curve points are in **actual MW**, evaluate at `P=70`.
  - If curve/segments are in **above-minimum**, evaluate at `p_above=20` and do *not* separately charge pmin energy unless specified.

A common bug that produces very expensive schedules:
- Charging `C(P)` (which already includes minimum-output cost) **and** adding `NoLoadCost*u` again.

### 5) Co-optimizing energy and spinning reserve without forcing extra commitment

Reserve must come from online thermal units, but it should be co-optimized with dispatch and commitment:
- Allow the model to trade off: (a) holding headroom on already-online units vs (b) starting additional units.
- In the objective, reserve is usually **free** unless the dataset includes a reserve cost. Therefore, commitment/dispatch must be allowed to adjust so that meeting reserve doesn’t require unnecessarily many online units.

Practical guidance:
- Enforce deliverability with `P + R ≤ pmax*u` and ramp on `P+R` (or above-min version) so reserve is feasible.
- Do **not** add artificial constraints like `R ≥ α*P` or “keep N units online” unless explicitly required.
- When reserve requirement is high, the cheapest solution may be: keep a few large/cheap units online with headroom and avoid many small expensive starts.

### 6) Economic red flags & how to diagnose from schedules

After you obtain a feasible schedule, scan for these red flags:
- **Too many units online**: many `u=1` with `P=pmin` for long blocks → likely reserve/commitment is over-constrained.
- **Excessive starts/stops**: frequent cycling without large demand swings → min up/down or startup-cost tiers misapplied, or objective missing startup costs.
- **Renewable curtailment while thermal marginal cost is high**: indicates a modeling error (e.g., renewables incorrectly constrained, or thermal forced on for reserve when headroom could be provided differently).
- **Flat dispatch despite piecewise costs**: suggests piecewise segments not modeled (or total-cost curve mistakenly linearized).
- **Units producing above pmin while cheaper units have headroom**: suggests cost curve evaluated on wrong MW convention or pmin energy double-count.

### 7) Required final step: recompute and reconcile reported cost before submission

Before writing the final report:
1. Recompute total cost from the exported arrays (`u,start,stop,P`) using the same conventions as the verifier expects.
2. Reconcile each component (startup, shutdown, no-load, energy) against your objective value.
3. If mismatch exists, fix the cost model (not the report). Only then set `summary.objective_cost`.
Use only cost components present in the data or required by the prompt. Do not invent no-load, reserve, curtailment, shutdown, or ramping costs.

For total-cost breakpoints:

```python
def total_cost_from_curve(points, output_mw):
    pts = sorted((p["mw"], p["cost"]) for p in points)
    if output_mw <= pts[0][0]:
        return pts[0][1]
    if output_mw >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= output_mw <= x1:
            return y0 + (output_mw - x0) * (y1 - y0) / (x1 - x0)
    raise ValueError("output outside curve")
```

If the first point is at minimum output, its cost may represent online minimum-output cost. Do not add another fixed online cost unless the data says so.

## Implementation Workflow

1. Parse and normalize resource/time arrays.
2. Choose actual-output or above-minimum internal variables and stick to it.
3. Include hard feasibility constraints before optimizing cost.
4. Extract the solution into the report convention.
5. Run independent validation on extracted arrays.
6. Recompute costs and summaries from arrays.
7. Write `"pass"` checks only after validation passes.


8. Run a final exported-schedule feasibility audit using the exact exported arrays (`commitment`, `startup`, `shutdown`, `production_MW`, `reserve_MW`). Recompute:
   - `p_above_min = production_MW - pmin * commitment`
   - startup/shutdown derated capability,
   - `production + reserve` or `p_above_min + reserve` limits,
   - ramping with reserves included,
   - offline zero conditions.
   Do not rely only on internal solver variables; exported schedules can become inconsistent after rounding, repair heuristics, or MW-convention conversions.


Add an explicit economic sanity pass (recommended for this benchmarked task type):

8. Compare your recomputed total cost against simple baselines:
   - all-renewables-used + cheapest thermals to cover net load,
   - no unnecessary startups,
   - dispatch roughly follows marginal costs.
   If cost is far above expectations, revisit piecewise cost modeling, pmin/no-load conventions, and reserve-driven commitment.
## Common Pitfalls

- Treating UC as independent hourly dispatch.
- Counting reserve from offline units or renewable headroom.
- Checking reserve headroom but forgetting startup or ramp deliverability.
- Ignoring initial output in first-period ramping.
- Ignoring initial on/off duration in minimum up/down constraints.
- **Cost-curve convention mismatch** (evaluating curve on above-min when it expects actual MW, or vice versa).
- **Double-counting minimum-output cost** (charging a total-cost curve at `P` and also adding a separate no-load/min-output cost).
- **Omitting piecewise segments** and using a single marginal cost (often yields the wrong merit order and commitment).
- **Over-committing to satisfy reserve** due to unnecessary constraints; failing to let energy+reserve co-optimize.
- Trusting a repair LP that omits a constraint family.
- Hard-coding `"pass"` fields before validation.
