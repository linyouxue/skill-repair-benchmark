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



### Deterministic Indexing For UC रिपोर्ट/Verifier Compatibility

For unit commitment, the verifier/report typically assumes stable `(generator, hour)` ordering.

- Preserve generator order exactly as read from input (store `thermal_names`, `renewable_names`).
- Use a fixed hour index convention internally (either `t=0..T-1` or `t=1..T`), then convert at report time. The sample report uses `hour` starting at **1**.
- For any additional dimensions (e.g., piecewise segments `s`), fix a deterministic segment order from input breakpoints.

**Recommended map keys:**

- `u[g,t]` commitment (binary)
- `p[g,t]` total MW production (not “above minimum” unless explicitly modeled that way)
- `r[g,t]` spinning reserve MW
- `su[g,t]`, `sd[g,t]` startup/shutdown (binary)
- `seg[g,t,s]` piecewise segment quantities

Maintain a single source of truth for index ↔ name mapping and reuse it for extraction and JSON serialization.

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



## UC-Sized Solve Settings (900s) And Solver Fallback

Unit commitment instances are often large; plan for a feasible incumbent under a time limit.

**Solver selection / fallback order** (use the best available in the environment):

1. Prefer a dedicated MILP solver if installed (e.g., CBC via PuLP, OR-Tools CP-SAT for pure MILP-like encodings, or Pyomo+CBC/HiGHS). 
2. Otherwise use HiGHS via SciPy `milp`.
3. If no MILP solver is available, stop and report that no feasible MILP solve is possible (do not fabricate results).

**Always set (at least):**

- `time_limit` close to the end-to-end budget (e.g., 800–880s to leave time for extraction/validation/JSON writing).
- a relative MIP gap target (e.g., `mip_rel_gap=0.005` to `0.02`) so the solver can stop early with a controlled bound.
- single-thread / deterministic settings when available (`threads=1`, fixed random seed) to stabilize indexing/debugging.

**Availability check pattern:**

- Before building a large model, confirm the solver module imports and can run a tiny MILP.
- Log solver name/version and key options used so failures are diagnosable.

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



### Termination Mapping To Report Status Strings

Map solver termination to the required `summary.solver_status` values:

- `optimal`: proven optimal.
- `feasible`: proven feasible and solved to completion but not proven optimal (e.g., stopped by gap criterion with proof).
- `time_limit_feasible`: hit time limit **and** an incumbent exists.
- `suboptimal_feasible`: solver stopped for another non-error reason (node limit, memory) with incumbent.
- `heuristic_feasible`: constructed by heuristic/repair without MILP proof (still must validate).

Rules:

- If **no incumbent** exists, do not write a schedule.
- Set `reported_mip_gap` to a nonnegative float only if the solver provides a trustworthy value; otherwise set to `null`.
- When a bound is available: `gap = max(0, (incumbent - best_bound) / max(1.0, abs(incumbent)))` for minimization, but only if the solver’s bound is valid.

## Extraction And Validation



### Incumbent Extraction Under Time Limit (No Unsafe Rounding)

When the solver stops early, prefer the incumbent as-is.

- Only round binaries/integer variables if they are within tolerance of an integer, e.g. `abs(x-round(x)) <= 1e-6` (or solver integrality tolerance). Otherwise treat as an invalid extraction and re-solve/repair.
- After rounding, **revalidate all constraints**; if violations increase materially, undo rounding and use the raw incumbent or run a repair MILP/LP that includes *all* verifier-checked families.

### Post-Solve Recompute (Verifier-Friendly)

Implement a validation module that reads **only**: input data + extracted arrays (commitment/production/reserve/startup/shutdown/renewables). It must recompute and record:

- `max_demand_balance_violation_MW`
- `max_reserve_shortfall_MW`
- maximum generator-limit violation (min/max output, offline zero production/reserve)
- ramping violations
- minimum up/down and transition-logic violations
- must-run and initial-condition violations
- renewable min/max violations

Also recompute objective cost from extracted arrays (no-load, startup, variable/segment costs) and ensure it matches `summary.objective_cost` within a small tolerance; otherwise fix reporting or rerun.

### JSON Serialization Checklist (UC)

Before writing `/root/report.json`:

- Arrays have exact length `T` for every generator.
- `hourly_summary[k].hour == k+1`.
- Generator `name` strings exactly match input.
- Values are plain JSON numbers (no NaN/Inf); use `null` only where allowed (e.g., `reported_mip_gap`).
- Recompute totals (`total_startups`, `total_shutdowns`, hourly sums) from arrays rather than trusting solver callbacks.

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
