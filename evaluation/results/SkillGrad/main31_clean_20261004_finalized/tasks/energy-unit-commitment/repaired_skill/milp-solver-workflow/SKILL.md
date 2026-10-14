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

Before finalizing any grader-facing artifact, enforce an **optimality gate**: accept the solve only if the solver reports optimality, or if its reported MIP gap is at or below your task’s acceptable tolerance.

Read references/optimality-gate-and-resolve-loop.md when the task is scored on objective quality and the solver can stop with a time limit / nonzero MIP gap. Skip when the solver is guaranteed to run to optimality (no time limit, or exact optimal status is required and already reached).

## Extraction And Validation

After solving:

- check binary variables are close to 0/1 before rounding;
- convert internal units/conventions to report units;
- recompute summaries from arrays;
- recompute objective from input data and extracted decisions;
- run validation that reads only input data plus extracted/report arrays;
- write `"pass"` self-checks only after validation passes.

Decision rule: if there is no feasible incumbent (`result.x is None` or solver reports infeasible), **do not write** the final report; instead write a diagnostic note and enter the infeasibility-debug path.

## Debugging Infeasibility

First suspect the model encoding. Common causes:

- mixing total output with output above minimum;
- applying startup/shutdown limits to the wrong quantity;
- using the wrong `t` or `t-1` index;
- over-constraining initial minimum up/down obligations;
- enforcing post-horizon obligations when the prompt excludes them;
- treating cost curves as feasibility constraints;
- choosing bad Big-M values;
- requiring tier variables without modeling the state that triggers them.

When the **LP relaxation is feasible but the MILP is infeasible**, prioritize debugging integer/logic constraint families.

Algorithmic checklist:

1. Confirm basic bounds and data sanity (no negative or inverted limits).
2. Disable all integrality and solve the LP relaxation; keep its solution for comparison.
3. Re-enable integrality and isolate by constraint family: temporarily relax/remove one family at a time (transition linking, minimum up/down windows, ramp with start/stop coupling, reserve deliverability, tier logic) and re-solve.
4. If isolation is slow, add nonnegative slack variables per family with a large objective penalty; re-solve and report which families use slack.
5. Remove or simplify heuristic tier/logic add-ons until a consistent base UC is feasible; then reintroduce features one at a time.

Read references/infeasibility-debug-by-family.md when the MILP is infeasible (especially when LP relaxation is feasible) and you need a systematic isolation/slack workflow. Skip when the solver returns a feasible incumbent and only minor tolerance/rounding issues remain.

## Repair LPs And Heuristics

A fixed-commitment repair LP is useful only if it includes every feasibility family judged in the final report. Do not repair only balance and capacity while omitting transition-dependent ramp, reserve, startup, shutdown, or minimum-duration limits.

Always rerun independent validation after repair.

## Reporting Discipline

Write exactly the grader-facing report fields by recomputing them from the **final reported arrays** using one explicit definition per field.

```python
# After any rounding and unit conversions, compute report arrays once.
u_rep = u_rep.astype(int)

prev = initial_on.astype(int)
start_rep = ((u_rep == 1) & (prev[:, None] == 0)).astype(int)
stop_rep  = ((u_rep == 0) & (prev[:, None] == 1)).astype(int)

# (generic placeholder) update prev across time in your implementation
# and keep start/stop definitions consistent with that update.

assert np.all(u_rep[:, 0] - initial_on == start_rep[:, 0] - stop_rep[:, 0])
assert np.all(start_rep + stop_rep <= 1)

total_startups = int(start_rep.sum())
total_shutdowns = int(stop_rep.sum())
```

Decision rule: if you change binaries during extraction (rounding, fixing tiny negatives, projecting), treat the changed arrays as the new source of truth and recompute *all* transition indicators, totals, and summaries from them, then revalidate.

Read references/report-field-parity.md when the report contains aggregate counters (e.g., startups/shutdowns) derived from transitions or initial conditions. Skip when the report is purely per-period variables with no derived summary fields.

## Common Pitfalls

- Interpreting MILP infeasibility as “the data are impossible” without first isolating the conflicting constraint family.
- Treating a feasible incumbent at a time limit as “good enough” without checking solver optimality or a benchmark-acceptable MIP gap.
- Rounding binaries and then mixing pre-round and post-round values when computing summaries.
- Writing aggregate fields that are not recomputed from the same arrays written to the report.
- Validating feasibility families but skipping a final parity check on grader-compared report fields.
