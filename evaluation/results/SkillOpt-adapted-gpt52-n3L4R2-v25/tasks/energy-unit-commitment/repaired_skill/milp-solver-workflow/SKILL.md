---
name: milp-solver-workflow
description: Use for formulating, solving, debugging, and validating mixed-integer linear optimization models with open-source solvers, including variable indexing, sparse constraints, linearized costs, solver limits, MIP gaps, incumbent extraction, numerical tolerances, and deterministic output reporting.
---

# MILP Solver Workflow

Use this skill for binary/integer decisions, linear constraints, and linear or piecewise-linear objectives. It is useful for time-expanded scheduling models with many repeated resource-period constraints.

This is a workflow and implementation guide, not a complete formulation for any one task.

## Workflow

1. Parse and normalize data into ordered arrays.
2. Define decision states before coding: status, transitions, continuous quantities, slacks, segments, tiers.
3. Build a deterministic variable map.
4. Add constraints family by family: bounds, linking, balance, time coupling, capacity/ramp limits, cost logic.
5. Solve with an available open-source MILP solver.
6. Extract a candidate solution, rounding binaries only if near integral.
7. Convert internal variables into the report convention.
8. Independently validate extracted arrays.
9. Recompute objective and summaries from extracted arrays.
10. Write final output only after validation passes.

## Variable Map Pattern

Use helper functions or dictionaries, not scattered index arithmetic.

```python
offset = {}
n = 0

def alloc(name, shape, lb=0.0, ub=float("inf"), integer=False):
    global n
    size = int(np.prod(shape))
    idx = np.arange(n, n + size).reshape(shape)
    offset[name] = idx
    n += size
    return idx

u = alloc("commitment", (G, T), lb=0, ub=1, integer=True)
start = alloc("startup", (G, T), lb=0, ub=1, integer=True)
dispatch = alloc("dispatch", (G, T), lb=0)
reserve = alloc("reserve", (G, T), lb=0)
```

Keep variable ownership obvious: type, resource, period, and optional segment/tier.

## Sparse Constraint Pattern

Use sparse rows for large time-expanded models:

```python
rows, cols, vals = [], [], []
lb, ub = [], []
row = 0

def add_row(terms, lo, hi):
    global row
    for j, a in terms:
        if abs(a) > 0:
            rows.append(row)
            cols.append(j)
            vals.append(float(a))
    lb.append(float(lo))
    ub.append(float(hi))
    row += 1
```

Use equality rows for conservation/linking and upper/lower bound rows for capacity, reserve, ramping, timing, and logic.

## Sign-Safe Encoding

Write the intended inequality first, then move variable terms to the left-hand side.

```python
# Intended: x + y <= cap * u - reduction * start
# Row form: x + y - cap*u + reduction*start <= 0
add_row(
    [(x, 1.0), (y, 1.0), (u, -cap), (start, reduction)],
    lo=-INF,
    hi=0.0,
)
```

For non-obvious rows, test a tiny hand case. Example: set `u=1`, `start=1` and check the remaining capacity equals the intended startup capability; set `u=1`, `start=0` and check normal capacity returns.

## Match Model Rows To Validation

Keep a checklist linking each model constraint family to a validation check:

```text
transition linking      -> startup/shutdown match status
online capacity         -> offline zeroes and min/max output
joint reserve capacity  -> production plus reserve fits capability
ramp deliverability     -> reserve can be deployed within ramp-up
minimum durations       -> starts/stops imply required status windows
balance equations       -> demand/load/inventory conservation
cost-curve logic        -> recomputed objective matches report
```

If validation checks something not in the model, the solver may produce an invalid report. If the model has a constraint not validated after extraction, conversion bugs can slip through.

## Piecewise-Linear Costs

Identify the curve convention before modeling:

- total cost at output breakpoints;
- marginal or incremental segment cost;
- heat-rate curve;
- first point as minimum-output or no-load-like cost.

For segment variables, constrain segment quantities to their widths and sum them to the modeled production quantity. Use slopes only when the data represents total-cost breakpoints or incremental segment costs consistently.

## Open-Source Solver Use

HiGHS through SciPy is a common default when available:

```python
from scipy.optimize import milp, LinearConstraint, Bounds

result = milp(
    c=c,
    integrality=integrality,
    bounds=Bounds(lb, ub),
    constraints=constraints,
    options={"time_limit": 600.0, "mip_rel_gap": 0.01, "disp": False},
)

if result.x is None:
    raise RuntimeError(f"No incumbent: status={result.status}, message={result.message}")
```

Capture status, objective, incumbent values, and any reliable gap/bound. A time-limit status can be useful if a feasible incumbent exists; a failure with no incumbent is not a solution.

## Extraction And Validation

After solving:

- check binary variables are close to 0/1 before rounding;
- convert internal units/conventions to report units;
- recompute summaries from arrays;
- recompute objective from input data and extracted decisions;
- run validation that reads only input data plus extracted/report arrays;
- write `"pass"` self-checks only after validation passes.

## Debugging Infeasibility

First suspect the model encoding. Common causes:

- mixing total output with output above minimum;
- applying startup/shutdown limits to the wrong quantity;
- using the wrong `t` or `t-1` index;
- over-constraining initial minimum up/down obligations;
- enforcing post-horizon obligations when the prompt excludes them;
- treating cost curves as feasibility constraints;
- choosing bad Big-M values;
- requiring segment/tier variables when the trigger did not occur.

Debug in stages: check shapes, relax one family at a time, add diagnostic slack variables, print largest violations, and compare local validation with final requirements.

## Repair LPs And Heuristics

A fixed-commitment repair LP is useful only if it includes every feasibility family judged in the final report. Do not repair only balance and capacity while omitting transition-dependent ramp, reserve, startup, shutdown, or minimum-duration limits.

Always rerun independent validation after repair.

## Reporting Discipline

- Use deterministic ordering and plain numeric values.
- Do not include placeholder values.
- Keep feasibility separate from proof quality/MIP gap.
- Use `null`/empty gap when no reliable bound exists, if the schema allows it.
- Do not trust solver status or self-reported `"pass"` strings without validation.



## End-to-End Unit-Commitment Data And Variable Contract

For a case such as `/root/network.json`, inspect and preserve the input before constructing the model: keep original generator names and source order, separate thermal and renewable generators, and assert that demand, reserve, availability, and every required time series cover exactly 48 periods. Use zero-based internal periods `t=0..47` but report `hour=t+1`. Build one deterministic keyed map for every modeled quantity, for example `x[('u', g, t)]`, `x[('start', g, t)]`, `x[('stop', g, t)]`, `x[('p_above_min', g, t)]` or `x[('p_total', g, t)]`, `x[('reserve', g, t)]`, `x[('renewable', r, t)]`, `x[('curtailment', r, t)]`, `x[('startup_tier', g, t, k)]`, and `x[('cost_segment', g, t, k)]`. Allocate and extract only through these maps; never reconstruct ownership from flattened offsets or report position. Decide once whether thermal output is total MW or above-minimum MW. If using above-minimum output, define `p_total[g,t] = pmin[g]*u[g,t] + p_above_min[g,t]` and use `p_total` for reporting, balance, ramping, reserve deliverability, and cost links. Assert unique names, finite numeric inputs, valid bounds, and exact dimensions before adding any solver rows.



## Complete UC Row-Family Build And Audit

Construct and count/log each row family rather than relying on a partial formulation. Add: variable bounds and integrality; renewable production and curtailment/availability links; hourly demand balance; system spinning-reserve requirement; thermal online minimum and maximum limits; production-plus-reserve capability; reserve deliverability from online thermal headroom and ramp capability; must-run constraints; startup/shutdown transition equations for every period; initial commitment, initial output, and initial elapsed up/down conditions; minimum-up and minimum-down windows including the precise horizon-edge convention; startup and shutdown output limits; ramp-up and ramp-down limits using the same total-output convention as the report; startup-tier selection and offline-duration links; piecewise cost-segment widths and production links; and all no-load, production, startup, shutdown, and curtailment cost terms. Keep a dictionary such as `family_rows[name]` with the number and indices of rows added. For each family, define an independent post-extraction check. A feasible schedule must satisfy, within documented tolerances, `sum(thermal_total)+sum(renewable)=demand`, reserve adequacy and deployability, online limits, transitions, initial conditions, duration windows, ramps, must-run, availability, and all cost links; do not label a check pass merely because the corresponding solver row existed.



## Incumbent Evidence And Non-Rounding Policy

After the MILP call, capture the solver status and message, whether an incumbent vector exists, incumbent objective, best bound, and a reliable relative gap if available. Reject `x is None` or any result without a feasible incumbent. Classify `optimal` only from a solver optimality certificate; classify a time-limit result with an incumbent as `time_limit_feasible`; use `suboptimal_feasible` only when another termination reason leaves a feasible incumbent and the evidence supports that label; otherwise use `feasible` or `heuristic_feasible` only when the construction method justifies it. Report a finite nonnegative gap only when computed from reliable objective/bound evidence; otherwise report JSON `null`. Before extraction, verify each binary/integer value is within an explicit tolerance of an allowed integer. Reject materially fractional commitments, starts, stops, tier selectors, or segment selectors instead of silently rounding them. If near-integral values are normalized to 0/1, rerun every independent feasibility and objective check on the normalized schedule and abort if any check changes from pass.



## Verifier-Contracted Extraction And Atomic Reporting

Create the report only from the validated extracted arrays. Convert internal thermal variables to actual total MW exactly once, preserve input names and source order, and assert that every commitment, production, reserve, startup, shutdown, and renewable-production array has exactly 48 elements. Independently recompute all hourly balances, reserve shortfalls, generator-limit violations, renewable limits, must-run, ramps, transitions, initial conditions, minimum up/down obligations, and startup/shutdown logic from the input data plus extracted arrays; independently recompute no-load, production, piecewise, startup-tier, shutdown, and any curtailment costs and compare that total with the reported objective within an explicit tolerance. Derive `hourly_summary`, startup/shutdown totals, thermal and renewable totals, maximum violations, generator counts, and all `constraint_check` values from those same arrays; set a check to `pass` only after its independent calculation passes. Validate original names, numeric finiteness, JSON-safe null-or-number gap, exact 48-hour shape, and the allowed solver-status vocabulary. Serialize to a temporary file, parse it back, revalidate the schema and values, and atomically rename it to `/root/report.json` only after every check and consistency comparison succeeds; never emit a placeholder or partially validated report.
