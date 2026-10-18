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


   - For routing plus inventory models, tighten variable bounds aggressively from data-derived limits instead of using loose big-M values.
   - Add explicit linking constraints between visits/arcs and pickup-dropoff-flow variables so service is impossible without a selected visit.
   - Propagate vehicle load and station inventory through every stop with hard lower and upper bounds at each transition state.
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



# Optional benchmark-oriented tuning.
for name, value in [
    ("limits/time", 300.0),
    ("limits/gap", 0.01),
    ("emphasis/mip", 1),
    ("heuristics/emphasis", "fast"),
    ("separating/maxrounds", 10),
]:
    try:
        model.setParam(name, value)
    except Exception:
        pass
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


Also link station service quantities to routing decisions. Typical examples include:

```python
# Service only if vehicle visits station.
model.addCons(pickup[k, i] <= max_pickup[i] * visit[k, i])
model.addCons(dropoff[k, i] <= max_dropoff[i] * visit[k, i])

# Tight inventory bounds.
model.addCons(total_pickup[i] <= initial_bikes[i])
model.addCons(initial_bikes[i] - total_pickup[i] + total_dropoff[i] <= station_capacity[i])
```

These constraints prevent infeasible inventory extraction and usually strengthen the LP relaxation.
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


## Competitive Solving For Benchmark Tasks

For benchmark-style routing and flow MIPs, solver configuration and incumbent construction often matter as much as the base formulation.

### SCIP Parameterization

Use explicit limits and emphasis settings instead of relying on defaults.

```python
set_if_available(model, "limits/time", 300.0)
set_if_available(model, "limits/gap", 0.01)
set_if_available(model, "limits/absgap", 1e-6)

# Push SCIP toward finding and improving incumbents quickly.
set_if_available(model, "emphasis/mip", 1)
set_if_available(model, "heuristics/emphasis", "fast")
set_if_available(model, "heuristics/rens/freq", 10)
set_if_available(model, "heuristics/undercover/freq", 10)
set_if_available(model, "heuristics/zeroobj/freq", 5)

# Presolve, cuts, and propagation are usually valuable for routing/flow models.
set_if_available(model, "presolving/maxrounds", 10)
set_if_available(model, "separating/maxrounds", 10)
set_if_available(model, "propagating/maxrounds", 10)

# Symmetry handling can help on multi-vehicle formulations.
set_if_available(model, "misc/usesymmetry", 1)
```

### Construct And Inject An Initial Incumbent

Do not rely exclusively on SCIP to discover the first feasible routing plan.
Construct a greedy or repair-based incumbent first, then pass it into SCIP as a MIP start.

```python
sol = model.createSol()

for (k, i, j), var in x.items():
    model.setSolVal(sol, var, initial_arc_values.get((k, i, j), 0.0))

for key, var in flow.items():
    model.setSolVal(sol, var, initial_flow_values.get(key, 0.0))

accepted = model.addSol(sol, free=True)
print("initial solution accepted:", accepted)
```

A simple nearest-neighbor route construction plus greedy pickup/dropoff balancing is often enough to give SCIP a strong incumbent.

### Incumbent Polishing And Re-Solve

After the first solve, extract routes and improve them outside the solver.

- Apply lightweight local search such as 2-opt, relocate, swap, or station reassignment.
- Recompute travel distance and unmet-demand penalties after every modification.
- Feed the improved incumbent back as another MIP start.
- Optionally fix stable routing decisions to reduce search space during polishing.

```python
# Example: fix selected incumbent arcs during a polishing solve.
for key, var in x.items():
    if incumbent_arc_values[key] > 0.5:
        model.fixVar(var, 1.0)

model.optimize()
```

On small benchmark instances, one or two polish-and-resolve iterations can close the gap between a merely feasible answer and a verifier-competitive incumbent.

### Final Objective Reconciliation Checklist

Before writing `report.json`, independently recompute and compare:

- total great-circle travel distance using radius 3960.0;
- station net bike changes and unmet amounts;
- unmet-demand penalty;
- objective = travel distance + penalty;
- vehicle load transitions and final station inventories.

Reject the export if any reconstructed component differs from the reported values by more than a small floating-point tolerance.


## Mandatory Independent Post-Solve Validation

Do not emit `report.json` directly from SCIP variable values without a full reconstruction pass.

Rebuild routes, station aggregates, and load trajectories from the exported solution and independently verify:

- every vehicle route starts and ends at the depot;
- no vehicle visits the same station twice;
- each stop satisfies `load_after_stop = previous_load + pickup - dropoff`;
- every vehicle load remains within `[0, vehicle_capacity]`;
- every station final inventory `initial_bikes - pickup + dropoff` remains within `[0, station_capacity]`;
- no station pickup exceeds available initial inventory;
- visit-linking constraints hold in the exported solution;
- objective components (travel distance, unmet penalties, total objective) exactly match recomputation within tolerance.

Abort export or raise an error if any reconstructed constraint or objective component disagrees with the report.

For benchmark competitiveness, consider a polishing phase after the first incumbent:

- fix or bias stable route/visit decisions and reoptimize flows;
- apply lightweight local route improvement such as 2-opt or relocate while preserving feasibility;
- feed improved incumbents back into SCIP as additional starts.
