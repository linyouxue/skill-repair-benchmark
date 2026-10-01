---
name: scip-opt
description: SCIP optimization with PySCIPOpt, including modeling, solving, validating, and committing required output artifacts for benchmark graders.
---

# SCIP Optimization

Use SCIP through `pyscipopt` when a task asks you to minimize or maximize an objective subject to constraints.

SCIP is a strong open-source optimization solver with a Python API. It is well suited for mixed-integer optimization, routing-style models, assignment models, capacity planning, inventory movement, scheduling, and problems with soft penalties. For benchmark tasks, a SCIP-backed model plus an independent validator is usually safer than a greedy construction.

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

8. Commit the output artifact.
   - Reserve the last step for output commit.
   - Never terminate the run until the deliverable exists on disk and passes post-write readback checks.
   - If optimization is incomplete or fails, still emit a structurally valid deliverable using a fallback (e.g., trivial/empty routes, zero moves, or best-known incumbent) rather than ending with no file.

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

## Output Commit (Write The Deliverable)

Treat writing the required deliverable as a mandatory final phase and a hard gate before `end_turn`. Always produce the required file even if solving/modeling is incomplete.

```python
import json
from pathlib import Path

def commit_json(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True))
    loaded = json.loads(Path(path).read_text())
    if not isinstance(loaded, dict):
        raise ValueError("deliverable must be a JSON object")
    return loaded
```

Stop-the-line checklist (run unconditionally before termination):

- Assemble a payload that includes all required top-level keys.
- Ensure entity coverage: emit a record for every required entity (e.g., all vehicles, all stations) even if some records are empty/default.
- **If no solver incumbent / time ran out:** still build a minimal structurally valid payload (empty routes, zero moves, numeric types) rather than producing no file.
- Write the file and immediately read it back.
- Re-run required-keys + entity-coverage checks on the parsed object.

If any check fails, repair the payload and re-commit; do not terminate.

Read references/output-commit-report-json.md when the required deliverable is a JSON file artifact that must exist on disk at the end of the run. Skip when the deliverable is not a file (e.g., purely printed output) or is guaranteed to be produced by an external harness.

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

## Common Pitfalls

- Ending a run without writing the required deliverable file; treat output writing as an explicit commit phase with a write-and-readback check plus required-keys/entity-coverage validation.
- Using Python `abs()` on solver expressions instead of linearizing absolute deviation.
- Missing subtour elimination when using binary arc routing variables.
- Confusing external IDs with internal 0..n-1 indices when building variables and reporting solutions.
