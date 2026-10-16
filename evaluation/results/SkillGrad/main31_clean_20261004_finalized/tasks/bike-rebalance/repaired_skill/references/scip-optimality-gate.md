# SCIP optimality gate (PySCIPOpt)

Use this chapter when the task is graded on objective quality (not just feasibility) and you are using SCIP with a time limit, a nonzero MIP gap, or a formulation/semantics choice that might admit a better incumbent under the benchmark’s intended interpretation.

## Procedure: check status, bound, and gap before finalizing

```python
import math

def scip_solution_metrics(model):
    status = str(model.getStatus()).lower()
    has_incumbent = model.getNSols() > 0

    obj = float(model.getObjVal()) if has_incumbent else math.inf

    try:
        best_bound = float(model.getBestbound())
    except Exception:
        best_bound = None

    gap = None
    if has_incumbent and best_bound is not None and math.isfinite(obj) and obj != 0.0:
        gap = abs(obj - best_bound) / abs(obj)

    return {
        "status": status,
        "has_incumbent": has_incumbent,
        "obj": obj,
        "best_bound": best_bound,
        "gap": gap,
    }


def require_optimal_or_tight_enough(model, max_gap=1e-4):
    m = scip_solution_metrics(model)
    if not m["has_incumbent"]:
        raise RuntimeError(f"no feasible solution; status={m['status']}")

    # Branch A: proven optimal (or solver says so) → accept
    if "optimal" in m["status"]:
        return m

    # Branch B: time/limit/stopped → require numeric gap bound
    if m["gap"] is None or m["gap"] > max_gap:
        raise RuntimeError(
            f"not proven optimal: status={m['status']} obj={m['obj']} bound={m['best_bound']} gap={m['gap']}"
        )
    return m
```

### Runtime branch: what to do if the gate fails

- If `has_incumbent` is false: relax contradictory constraints, add missing feasibility slack, or fix data/mappings; then re-solve.
- If `status` is not optimal and `gap` is missing/high:
  1) increase time limit; 2) tighten formulation (e.g., stronger connectivity/subtour constraints); 3) add valid bounds / tighter Big-M; then re-solve and compare objective values.

## Vehicle usage semantics (optional vs required)

When routing resources (vehicles/crews) may be unused, prefer an explicit activation variable linked to depot start/end constraints; when usage is required, enforce departure/return equalities.

```python
from pyscipopt import quicksum

use = {k: model.addVar(vtype="B", name=f"use_{k}") for k in vehicles}

for k in vehicles:
    model.addCons(quicksum(x[k, START, j] for j in locations) == use[k])
    model.addCons(quicksum(x[k, i, END] for i in locations) == use[k])
```

Runtime branch:

- If the statement/evaluator requires every vehicle to be used (e.g., “each vehicle must visit at least one station”), replace `== use[k]` with `== 1` (or add `use[k] == 1`) and keep the rest of the model unchanged.

## Conservation + initial/end load anchoring (closed system vs depot source/sink)

Many benchmarks expect you to *choose and encode* whether units are conserved within the system, and whether vehicles can start preloaded.

Checklist:

- Decide whether there is a true source/sink node (depot) for the commodity.
- If not, enforce conservation: total units in stations + units on vehicles is constant across the plan.
- Anchor vehicle start load (and typically end load) to the stated condition (often 0), rather than letting it float as a free decision variable.

```python
# Generic pattern: anchor initial load if vehicles start empty.
# (Use a depot node/time index or an explicit start-load variable, depending on your model.)
start_load = {k: model.addVar(vtype="I", lb=0, ub=cap[k], name=f"start_load_{k}") for k in vehicles}

# Branch A: vehicles start empty
for k in vehicles:
    model.addCons(start_load[k] == 0)

# Branch B: vehicles may start loaded from a limited depot supply
# depot_supply = model.addVar(vtype="I", lb=0, ub=depot_cap, name="depot_supply")
# for k in vehicles:
#     model.addCons(start_load[k] <= cap[k])
# model.addCons(quicksum(start_load[k] for k in vehicles) <= depot_supply)
```

Runtime branch:

- If your model currently allows arbitrary start loads (or arbitrary “bike creation” at the depot) and you see any positive unmet/deviation: treat this as a red flag and re-check whether the benchmark intended a closed system with fixed start loads.

## Post-solve quality probe when slacks remain

If any unmet/deviation/slack variables are positive, run a fast *quality probe* to detect “optimal for the wrong model / wrong scaling” before finalizing.

Two common probes:

1) **Lexicographic solve:** first minimize total unmet, then (fixing that minimum) minimize travel/cost.
2) **Penalty bump:** temporarily increase unmet penalties and see if unmet drops at a small cost increase.

```python
from pyscipopt import quicksum

# Suppose slack[i] is nonnegative unmet/deviation.
slack_total = quicksum(slack[i] for i in items)

# Branch A: lexicographic (two-phase) optimization
model.setObjective(slack_total, "minimize")
model.optimize()
min_slack = float(model.getObjVal())

model.freeTransform()
model.addCons(slack_total <= min_slack)  # allow numerical tolerance if needed
model.setObjective(original_cost_expr, "minimize")
model.optimize()

# Branch B: penalty bump (compare solutions)
# original_weight = w
# model.freeTransform(); model.setObjective(cost + (10*original_weight)*slack_total, "minimize"); model.optimize()
```

### Verification (post-solve, post-write)

Verification check:

1. Record `status`, `obj`, `best_bound`, and `gap` alongside the deliverable.
2. If any slack/unmet remains:
   - run a quality probe; if it finds a strictly lower slack/unmet with modest additional cost, **do not ship** the current solution;
   - next corrective action: revisit conservation/initial-load semantics, penalty scaling, and solve settings; then re-solve and re-extract.
