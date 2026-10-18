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


11. Before serializing/reporting, recompute every reported scalar (objective, startups, shutdowns, hourly totals, violations) directly from the final exported arrays that will appear in the report JSON; never reuse stale solver/model-side aggregates after schedule edits or repair passes.


### Objective & Benchmark Equivalence Debug Loop (do this before trusting “optimal”)

A MILP can be mathematically optimal for the *wrong* objective (wrong units, missing intercepts, double-counted pmin, wrong piecewise convention, etc.). Use this loop to force equivalence with the benchmark/accounting used by the verifier/report.

**A. Pre-solve: print objective coefficient summaries by variable family**

Before calling the solver, compute and print/inspect totals like:

- startup vars: min/median/max coefficient, count nonzeros, expected magnitude
- shutdown vars (if costed)
- no-load / online fixed cost terms (often proportional to commitment `u[g,t]`)
- energy / dispatch vars (or segment vars): slope ranges and units ($/MWh)
- reserve vars and penalties
- curtailment / load-shed / slack penalties (should be “very large” if prohibited)

Also check **signs** (penalties positive; revenues negative only if explicitly modeled) and **units** (MW vs MWh with time-step length).

**B. Post-solve: recompute total cost from extracted variables and assert match**

After extracting and converting to report conventions, recompute the full objective using the *same accounting as the benchmark/report*, then assert:

- `abs(cost_recomputed - cost_solver) <= atol + rtol*max(1, abs(cost_solver))`

If it fails, do not report a solution as competitive; fix the model/objective mapping first.


For unit commitment specifically, recomputation must explicitly include and reconcile:

- startup/shutdown costs by transition indicators;
- no-load/fixed online costs;
- piecewise or segmented production costs using the exact breakpoint convention;
- reserve costs/penalties and reserve deployment convention;
- renewable curtailment/load-shed/slack penalties;
- the distinction between actual MW and MW-above-minimum formulations.

If the exported report uses actual MW but the model optimizes above-minimum dispatch, convert consistently before recomputing costs and validating capacity/ramping inequalities.
**C. Piecewise / pmin / intercept spot-checks (common UC cost bugs)**

For a few generators-hours, manually spot-check:

- whether dispatch variable represents **total MW** or **MW above minimum**
- whether pmin is enforced and whether its cost is captured as:
  - no-load + incremental above pmin, or
  - segment curve that already includes pmin output
- piecewise segments:
  - activation constraints (segment quantities within widths)
  - slopes match the intended convention (incremental vs total-cost breakpoints)
  - intercepts are not missed or double-counted

If the data provides total cost at breakpoints, ensure you model either:
- incremental segments with correct derived slopes, or
- convex-combination/epigraph form consistent with totals.

**D. Economic sanity checks (post-solve)**

Run quick diagnostics that often reveal objective mistakes:

- merit-order consistency: expensive units shouldn’t run while cheaper units are available (unless constrained by min-up/down, ramps, must-run, reserve deliverability)
- overcommitment detection: too many online units at pmin with simultaneous renewable curtailment may indicate missing/low curtailment penalties or mis-modeled pmin costs
- renewable utilization: if curtailment exists, confirm it is explainable by min generation/reserve/ramp constraints, not by objective sign errors

**E. Compare against a lower bound / relaxed model to detect gross suboptimality**

Compute at least one cheap bound/relaxation:

- LP relaxation of the MILP (integrality off)
- or ED ignoring min-up/down and startup costs but respecting pmin/pmax and demand balance

If your MILP solution is far above a reasonable lower bound (e.g., >10–20% with mild constraints), suspect wrong objective or missing flexibility constraints.

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
    options={
        "time_limit": 600.0,
        "mip_rel_gap": 0.001,  # tighten for quality-sensitive benchmarks
        "disp": False,
    },
)

if result.x is None:
    raise RuntimeError(f"No incumbent: status={result.status}, message={result.message}")
```

### Solver-quality diagnostics and stopping rules

- Do not stop at the first feasible incumbent when the task is judged on cost quality.
- Record and report (when available): best incumbent objective, best bound, and relative gap.
- Treat `time_limit` as acceptable **only** if you have a competitive incumbent and can state a nonnegative reported gap (or `null` if the solver gives no reliable bound).
- If the cost is far from a quick lower bound (LP relaxation / relaxed ED), increase time limit, tighten `mip_rel_gap`, and consider enabling stronger presolve/cuts/heuristics when supported by the solver API.

Capture status, objective, incumbent values, and any reliable gap/bound. A time-limit status can be useful if a feasible incumbent exists; a failure with no incumbent is not a solution.

## Extraction And Validation

After solving:

- check binary variables are close to 0/1 before rounding;
- convert internal units/conventions to report units;
- recompute summaries from arrays;
- deterministically recompute objective from input data and the exact exported/report arrays (not intermediate solver variables or cached totals);
- run validation that reads only input data plus extracted/report arrays;
- write `"pass"` self-checks only after validation passes.



### Cost consistency is necessary but not sufficient


After incumbent extraction, independently re-evaluate every operational inequality from the exported arrays only (not solver internals), including startup/shutdown-capacity reductions, reserve deliverability, ramping, minimum output, and transition logic. This is mandatory when binaries were rounded, repaired, edited after solve, or obtained from a time-limited incumbent.

Treat any post-processing modification to commitments, dispatch, reserve, or renewable schedules as invalidating previously stored objective values and validation summaries until they are recomputed from scratch.
Passing “reported cost matches extracted schedule” only proves internal consistency. Also require:

- objective-equivalence: solver objective equals independently recomputed cost (same accounting as report/verifier)
- competitiveness checks: compare against a lower bound/relaxation and run economic sanity checks (merit order, overcommitment, renewable utilization)

If any of these fail, treat the run as a modeling/debug iteration, not a final answer.

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
