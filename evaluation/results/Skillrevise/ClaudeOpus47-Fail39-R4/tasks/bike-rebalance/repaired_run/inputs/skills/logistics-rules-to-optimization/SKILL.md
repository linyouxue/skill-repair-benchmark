# Logistics Rules To Optimization

## Purpose
Translate operational rules (vehicles, depots, pickups/dropoffs, inventory, capacity, time windows, assignments, service targets) into a solver model, then verify the solution against a baseline before accepting it. The skill is a decision procedure, not a pattern catalog.

## When to Use
Use when a task gives operational rules in words and asks for an optimization model or an optimized plan. Do not use for pure data extraction, pure simulation, or when no decision variables are implied.

## Procedure
- Discover entities and features. List entities (vehicles, locations, periods, jobs). Record task features that drive modeling choices: split-service allowed? pickup and dropoff at same node allowed? vehicles mandatory or optional? time windows present? inventory bounds per node?
- Choose formulation (log the decision in one line).
- If a node can be both pickup and dropoff in one visit OR net movement is what matters: use a single signed service variable `service[v,i]` with `lb=-cap, ub=cap`.
- Else if pickup and dropoff are mutually exclusive per visit: use two nonneg vars `pickup[v,i]`, `dropoff[v,i]` with a binary selector.
- If the task says "a vehicle must visit some station": use optional vehicle usage `use_vehicle[v]` and tie depot arcs to it; do not hard-code `== 1` unless the text says every vehicle must be used.
- Build variables and constraints using exactly one of each needed pattern:
- Arc binaries `x[v,i,j]`; route continuity `in == out`; at-most-once `out <= 1`.
- Load/time propagation along selected arcs with big-M from real bounds (one pattern only).
- Node inventory feasibility: aggregated net change at node `i` must lie in `[-free_space[i], initial_inventory[i]]`.
- Soft targets via nonneg slack with two-sided absolute-deviation constraints (never Python `abs`).
- Subtour elimination (MTZ or cut-based) whenever arc routing has >2 non-depot nodes.
- Assemble a named objective: `travel_cost + fixed_cost + penalty_cost`. Keep components separate so you can inspect them.
- Verify against two baselines before returning:
- Lower bound on unmet demand: sum of per-node shortfalls that cannot be covered by any other node's surplus given inventory limits. Solver `unmet` must equal this LB.
- Upper bound on travel: a greedy nearest-neighbor route serving the same set of nodes. Solver `travel_cost` must be <= greedy baseline.
- Print `{solver_obj, greedy_obj, lb_unmet, solver_unmet}`.
- Recover if verification fails: if `solver_obj > greedy_obj` or `solver_unmet > lb_unmet`, re-examine step 2 choices once (relax mandatory vehicles to optional, switch between signed-service and split pu/do, add missing subtour cuts), re-solve, and re-verify. Do not loop more than once; if still failing, return the model with an explicit note of the gap and the suspected cause.

## Constraints / Pitfalls
- Do not accept a feasible solution as optimal: a feasibility-only self-check caused the prior failure. Always print and compare against the greedy baseline and the unmet-demand lower bound.
- Do not use `== 1` for depot-leaving arcs unless the task explicitly says every vehicle must be used; default to `== use_vehicle[v]`.
- Do not mix signed service variables with separate pu/do binaries in the same model; pick one in step 2 and log why.
- Pick big-M from real variable bounds (capacity, time horizon). Never use arbitrary large constants.
- Never apply Python `abs()` to solver expressions; use two-sided slack constraints.
- Keep the global single-visit rule off unless the task forbids split service across vehicles.
- Do not hard-code instance literals (station ids, counts, coordinates) into the model structure.