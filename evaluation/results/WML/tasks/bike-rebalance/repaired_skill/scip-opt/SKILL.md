---
name: scip-opt
description: SCIP optimization with PySCIPOpt. Use when facing an optimization problem with an objective, hard constraints, soft penalties, integer decisions, routing, assignment, scheduling, allocation, packing, capacity, inventory, or service-level rules. Prefer modeling and solving the problem with PySCIPOpt when it is available.
---

# SCIP Optimization

Use SCIP through `pyscipopt` when a task asks you to minimize or maximize an objective subject to constraints.

SCIP is a strong open-source optimization solver with a Python API. It is well suited for mixed-integer optimization, routing-style models, assignment models, capacity planning, inventory movement, scheduling, and problems with soft penalties. For benchmark tasks, a SCIP-backed model plus an independent validator is usually safer than a greedy construction.

## When To Use

Consider PySCIPOpt when the request includes:

- an objective such as minimizing cost, distance, time, unmet demand, or penalty;
- yes/no choices, route arcs, assignments, selected items, or ordering decisions;
- integer or continuous quantities such as load, inventory, flow, served units, or slack;
- hard rules that every valid answer must satisfy;
- soft rules that can be violated with an explicit penalty.

Do not start by installing another optimization package. First check whether PySCIPOpt is already available:

```python
try:
    from pyscipopt import Model, quicksum
except ImportError as exc:
    raise RuntimeError("PySCIPOpt is required for this optimization approach") from exc
```

## Modeling Workflow

1. Identify sets and indices.
   - Examples: vehicles `K`, stations `N`, jobs `J`, periods `T`, arcs `A`.
   - Build explicit mappings when input IDs are not contiguous.

2. Define decision variables.
   - Binary variables for choices, visits, assignments, route arcs, or modes.
   - Integer variables for counts, loads, inventory moves, or unmet units.
   - Continuous variables for flows, costs, times, slacks, or resource levels.

3. Add hard constraints.
   - Conservation, capacity, bounds, linking, continuity, inventory limits, and mutual exclusion.

4. Add soft constraints with explicit slack variables.
   - Never use Python `abs()` on solver expressions.
   - Linearize absolute deviation with two inequalities.

5. Set a single objective.
   - Keep named objective components such as travel cost and penalty cost.

6. Solve with time and gap limits.
   - Require at least one incumbent before extracting a solution.

7. Reconstruct and independently validate the output.
   - Recompute objective components and every hard rule from the reported answer.

## Minimal PySCIPOpt Template

```python
from pyscipopt import Model, quicksum

model = Model("optimization_model")
model.hideOutput()

I = range(n_items)

x = {i: model.addVar(vtype="B", name=f"x_{i}") for i in I}
amount = {
    i: model.addVar(vtype="I", lb=0, ub=capacity[i], name=f"amount_{i}")
    for i in I
}
dev = {i: model.addVar(lb=0, name=f"dev_{i}") for i in I}

for i in I:
    model.addCons(amount[i] <= capacity[i] * x[i])
    model.addCons(amount[i] - target[i] <= dev[i])
    model.addCons(target[i] - amount[i] <= dev[i])

cost = quicksum(fixed_cost[i] * x[i] for i in I)
penalty = penalty_weight * quicksum(dev[i] for i in I)
model.setObjective(cost + penalty, "minimize")

model.setParam("limits/time", 300.0)
model.setParam("limits/gap", 0.01)
model.optimize()

status = str(model.getStatus()).lower()
if model.getNSols() == 0:
    raise RuntimeError(f"SCIP found no feasible solution; status={status}")

objective = float(model.getObjVal())
selected = [i for i in I if model.getVal(x[i]) > 0.5]
```

## Common Patterns

### Binary Activation

Use a binary variable to allow a quantity only when an option is active.

```python
use = {i: model.addVar(vtype="B", name=f"use_{i}") for i in I}
q = {i: model.addVar(lb=0, ub=upper[i], name=f"q_{i}") for i in I}

for i in I:
    model.addCons(q[i] <= upper[i] * use[i])
```

### Assignment

```python
assign = {
    (i, j): model.addVar(vtype="B", name=f"assign_{i}_{j}")
    for i in items
    for j in options
}

for i in items:
    model.addCons(quicksum(assign[i, j] for j in options) == 1)

for j in options:
    model.addCons(quicksum(weight[i] * assign[i, j] for i in items) <= capacity[j])
```

### Absolute Deviation Penalty

```python
dev = {i: model.addVar(lb=0, name=f"dev_{i}") for i in I}

for i in I:
    model.addCons(actual[i] - target[i] <= dev[i])
    model.addCons(target[i] - actual[i] <= dev[i])

penalty_cost = penalty_weight * quicksum(dev[i] for i in I)
```

### Route Arcs

```python
START = "depot_start"
END = "depot_end"
nodes_from = [START, *locations]
nodes_to = [*locations, END]
arcs = [
    (i, j)
    for i in nodes_from
    for j in nodes_to
    if i != j and not (i == START and j == END)
]

x = {
    (k, i, j): model.addVar(vtype="B", name=f"x_{k}_{i}_{j}")
    for k in vehicles
    for i, j in arcs
}

for k in vehicles:
    model.addCons(quicksum(x[k, START, j] for j in locations) == 1)
    model.addCons(quicksum(x[k, i, END] for i in locations) == 1)

    for i in locations:
        incoming = quicksum(x[k, j, i] for j in nodes_from if (j, i) in arcs)
        outgoing = quicksum(x[k, i, j] for j in nodes_to if (i, j) in arcs)
        model.addCons(incoming == outgoing)
        model.addCons(outgoing <= 1)
```

Degree and continuity constraints alone can permit disconnected cycles. Add subtour elimination for routing models.

### MTZ Subtour Elimination

```python
order = {
    (k, i): model.addVar(lb=1, ub=max(1, len(locations)), name=f"order_{k}_{i}")
    for k in vehicles
    for i in locations
}

n = len(locations)
for k in vehicles:
    for i in locations:
        for j in locations:
            if i != j:
                model.addCons(order[k, i] - order[k, j] + n * x[k, i, j] <= n - 1)
```

## Reproducibility

Fix SCIP randomization and thread settings when repeatability matters.

```python
def set_if_available(model, name, value):
    try:
        model.setParam(name, value)
    except Exception:
        pass

for name in [
    "randomization/randomseedshift",
    "randomization/permutationseed",
    "randomization/lpseed",
]:
    set_if_available(model, name, 0)

for name in ["randomization/permutevars", "randomization/permuteconss"]:
    set_if_available(model, name, False)

set_if_available(model, "parallel/maxnthreads", 1)
```

## Extraction And Validation

After solving, reconstruct the answer from variable values and validate it outside SCIP.

```python
def is_selected(var):
    return model.getVal(var) > 0.5

selected_arcs = [(i, j) for i, j in arcs if is_selected(x[vehicle, i, j])]
reported_cost = sum(distance[i, j] for i, j in selected_arcs)

if abs(reported_cost - expected_cost) > 1e-6:
    raise AssertionError("reported objective component does not match reconstruction")
```

Treat SCIP feasibility as necessary but not sufficient. The final reported file still needs independent checks for schema, route reconstruction, capacity, inventory, penalties, and objective arithmetic.

### Quality Gate: Verify Objective Acceptance Before Writeback

Some evaluators impose a *quantitative acceptance gate* on the objective (e.g., must be no worse than a reference incumbent within tolerance). In those settings, producing any feasible solution and validating arithmetic is not enough.

Add an explicit pre-write check:

1. **Compute a trusted reconstructed objective** from the candidate report (distance recomputed from coordinates + penalty recomputed from unmet amounts).
2. **Compare against an acceptance threshold** if one is provided or can be computed by a standardized reference run.
3. **Only write the final `report.json`** once the candidate passes the objective gate; otherwise continue improvement.

Practical pattern:

```python
best_report = None
best_obj = float("inf")

def reconstruct_objective(report) -> float:
    # Implement task-specific reconstruction: travel distance from geometry + penalty from unmet.
    ...

def passes_quality_gate(obj: float, threshold: float, tol: float = 1e-6) -> bool:
    return obj <= threshold + max(tol, tol * max(1.0, abs(threshold)))
```

### Fallback: Incumbent-Improvement Loop When Objective Is Slightly High

If feasibility and reconstruction checks pass but the objective is still above the required gate, treat it as an optimization problem, not a validation problem. Use a bounded improvement loop with a runtime cap and a monotone best-incumbent tracker:

- **Escalate solve effort**: increase `limits/time`, tighten `limits/gap`, or run a second phase with more search.
- **Warm start / reoptimize** using the current incumbent when possible.
- **Keep reproducibility** (fixed seeds, single thread), but allow controlled escalation of limits.

Example policy skeleton:

```python
# Phase A: get a feasible incumbent quickly
model.setParam("limits/time", 60.0)
model.setParam("limits/gap", 0.10)
model.optimize()

# Phase B: improve incumbent under a total time budget
for time_limit, gap in [(180.0, 0.05), (300.0, 0.02), (600.0, 0.01)]:
    if model.getNSols() == 0:
        break
    model.setParam("limits/time", time_limit)
    model.setParam("limits/gap", gap)
    model.optimize()

    candidate_report = extract_report_from_solution(model)
    candidate_obj = reconstruct_objective(candidate_report)

    if candidate_obj < best_obj:
        best_obj = candidate_obj
        best_report = candidate_report

    if HAVE_THRESHOLD and passes_quality_gate(best_obj, threshold_obj):
        break

if best_report is None:
    raise RuntimeError("no feasible solution extracted")

# Write best_report only after it passes all hard checks;
# when a quality gate exists, also require it before final writeback.
```

Scope boundary:

- Apply this quality gate and improvement loop **only when the evaluation explicitly grades objective quality** (thresholded/relative) rather than accepting any feasible solution.
- Do **not** skip feasibility and reconstruction checks; the quality gate is an *additional* step before final writeback.
