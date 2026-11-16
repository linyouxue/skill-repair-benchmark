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


## Benchmark-Competitive SCIP Workflow For Routing And Rebalancing

For vehicle routing, bike rebalancing, and inventory-routing tasks, a correct formulation alone is often not enough to beat verifier benchmarks under time limits. Prioritize obtaining strong incumbents early and improving them continuously.

### Recommended SCIP Parameters

Use explicit solve limits and heuristic settings instead of relying on defaults.

```python
model.setParam("limits/time", 300)
model.setParam("limits/gap", 0.01)

# Emphasize primal solution discovery.
model.setParam("heuristics/emphasis", "aggressive")
model.setParam("presolving/maxrounds", 10)
model.setParam("separating/maxrounds", 10)

# Useful for routing-style MIPs with many binaries.
model.setParam("branching/leastinf/priority", 1000)

# Keep logs available while tuning.
model.hideOutput(False)
```

If parameter names differ across SCIP versions, wrap `setParam` calls in `try/except` helpers.

For benchmark tasks, record both primal and dual bounds during experiments. A feasible solution with a small remaining gap is usually preferable to a model that never finds a strong incumbent.

### Build And Inject MIP Starts

Routing and bike-rebalancing models benefit heavily from warm starts.

Construct an initial feasible solution before optimization:

- greedy nearest-neighbor routes;
- depot-to-single-station routes for high-penalty stations;
- pickup-first then dropoff repair heuristics;
- route merges using savings-style logic;
- repairing infeasible routes instead of discarding them.

Inject the incumbent:

```python
sol = model.createSol()

for (k, i, j), var in x.items():
    model.setSolVal(sol, var, initial_x[k, i, j])

for key, var in load.items():
    model.setSolVal(sol, var, initial_load[key])

accepted = model.addSol(sol, free=True)
print("mip start accepted:", accepted)
```

Always verify that the warm start respects vehicle capacities, inventory balance, and route continuity before injection.



## Incumbent Improvement And Formulation Tightening

After SCIP finds a feasible solution, continue improving the incumbent instead of stopping at the first valid route set.

### Post-Solve Improvement Loop

A practical workflow is:

1. solve the MIP briefly to obtain a feasible incumbent;
2. reconstruct routes explicitly;
3. run local search improvements such as 2-opt, relocate, swap, or cross-exchange;
4. re-inject the improved incumbent as a new MIP start;
5. re-optimize with the remaining time budget.

For bike rebalancing, also try:

- moving small unmet quantities between nearby stations;
- consolidating lightly loaded vehicle routes;
- removing detours whose travel cost exceeds penalty savings.

When the benchmark tolerance is tight, these polishing passes can outperform a single long SCIP call.

### Strengthen Routing Formulations

Weak LP relaxations slow incumbent improvement.

Prefer tighter formulations and bounds:

- eliminate impossible arcs using distance or inventory logic;
- tighten big-M constants aggressively;
- bound vehicle loads and inventory variables as narrowly as possible;
- break symmetry by fixing vehicle ordering or forcing earlier vehicles to be used first;
- add valid inequalities such as degree tightening, capacity cuts, subtour cuts, or visit-limit cuts;
- forbid useless pickup-dropoff oscillations.

For inventory-routing problems, explicitly model feasible pickup/dropoff ranges derived from station inventory and capacity:

```python
pickup_ub = min(initial_bikes[i], vehicle_capacity)
dropoff_ub = min(station_capacity[i] - initial_bikes[i], vehicle_capacity)
```

### Troubleshooting Weak Incumbents

If SCIP stalls with a feasible but weak incumbent:

- inspect which stations contribute most unmet penalty;
- check whether travel cost scaling dominates penalties or vice versa;
- reduce symmetry and disconnected subtours;
- verify that vehicles are not carrying unnecessary residual load;
- test a smaller arc set using nearest-neighbor candidate edges;
- compare incumbent routes against a greedy baseline;
- increase heuristic emphasis before increasing total runtime.

For routing benchmarks, a high-quality feasible incumbent early in the solve is often more important than proving optimality.
