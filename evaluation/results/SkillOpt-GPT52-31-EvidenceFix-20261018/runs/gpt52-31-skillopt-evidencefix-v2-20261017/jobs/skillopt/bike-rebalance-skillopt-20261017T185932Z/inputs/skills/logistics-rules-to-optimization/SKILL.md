---
name: logistics-rules-to-optimization
description: Translate logistics and operations rules into optimization variables and constraints. Use when an operations problem describes vehicles, routes, depots, pickups, dropoffs, inventory, capacity, assignments, time windows, service targets, penalties, resource limits, or other business rules that need to become an optimization model.
---

# Logistics Rules To Optimization

Use this skill when the problem statement gives operational rules in words and the agent must turn them into an optimization model.

The goal is not only routing. The same translation pattern applies to transportation, dispatch, rebalancing, warehouse moves, staffing, scheduling, assignment, capacity planning, production, and service-level problems.

## Rule Translation Workflow

1. List the entities.
   - Examples: vehicles, locations, depots, jobs, workers, machines, products, arcs, time periods.

2. Choose the decision state.
   - Binary variables for yes/no choices.
   - Integer variables for counts, loads, inventory, units moved.
   - Continuous variables for time, flow, cost, utilization, or fractional quantities.

3. Convert each business rule into one of these patterns.
   - Conservation: what enters equals what leaves, plus/minus changes.
   - Capacity: quantity cannot exceed a limit.
   - Linking: a quantity is allowed only if a binary decision is active.
   - Assignment: exactly one, at most one, or at least one choice.
   - Sequence: if one action follows another, update load/time/state.
   - Compatibility: prohibit impossible combinations.
   - Soft penalty: add slack for unmet demand or violation cost.

4. Add the objective last.
   - Keep named components such as travel cost, labor cost, inventory penalty, unmet demand penalty.

5. Extract and independently validate the answer.
   - Recompute routes, loads, assignments, inventory, penalties, and objective from the output data.

## Variable Patterns

### Selection and Assignment

Use binary variables when an option is selected.

```python
x = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in I for j in J}
```

Common rules:

```python
# each item i assigned to exactly one option j
for i in I:
    model.addCons(quicksum(x[i, j] for j in J) == 1)

# option j can handle at most capacity[j] items
for j in J:
    model.addCons(quicksum(x[i, j] for i in I) <= capacity[j])
```

### Route Arcs

Use binary arc variables when the order of visits matters.

```python
x = {
    (v, i, j): model.addVar(vtype="B", name=f"x_{v}_{i}_{j}")
    for v in vehicles
    for i, j in arcs
}
```

Use `x[v, i, j] = 1` to mean vehicle/resource `v` goes directly from node `i` to node `j`.

### Visit Indicator

Define visit from route arcs instead of creating a second binary unless the model needs it repeatedly.

```python
visit = quicksum(x[v, i, j] for j in to_nodes if j != i)
```

If a standalone variable is useful:

```python
visit = {(v, i): model.addVar(vtype="B", name=f"visit_{v}_{i}") for v in vehicles for i in locations}

for v in vehicles:
    for i in locations:
        model.addCons(visit[v, i] == quicksum(x[v, i, j] for j in to_nodes if j != i))
```

### Quantity, Load, Inventory, and Time

```python
load = {(v, i): model.addVar(vtype="I", lb=0, ub=vehicle_capacity, name=f"load_{v}_{i}") for v in vehicles for i in nodes}
service = {(v, i): model.addVar(vtype="I", lb=-vehicle_capacity, ub=vehicle_capacity, name=f"service_{v}_{i}") for v in vehicles for i in locations}
inventory = {(i, t): model.addVar(vtype="I", lb=0, ub=storage_capacity[i], name=f"inventory_{i}_{t}") for i in locations for t in periods}
arrival = {(v, i): model.addVar(vtype="C", lb=0, name=f"arrival_{v}_{i}") for v in vehicles for i in nodes}
```

Use integer variables for physical unit counts when the output must be integer-valued.

## Common Logistics Rules

| Business Rule | Variable Choice | Constraint Pattern |
| --- | --- | --- |
| Choose exactly one option | `x[i,j]` binary | `sum_j x[i,j] == 1` |
| Choose at most one option | `x[i,j]` binary | `sum_j x[i,j] <= 1` |
| Open facility before assigning to it | `open[j]`, `assign[i,j]` binary | `assign[i,j] <= open[j]` |
| Resource capacity | quantity variable | `sum_i q[i,j] <= capacity[j]` |
| Quantity only if selected | `q[i]`, `use[i]` | `q[i] <= M * use[i]` |
| Fixed cost if used | `use[i]` binary | add `fixed_cost[i] * use[i]` to objective |
| Mutually exclusive modes | mode binaries | `sum_m mode[i,m] <= 1` |
| Incompatible pair | two binaries | `x[a] + x[b] <= 1` |
| Demand must be met | flow/quantity | `supply_to[i] >= demand[i]` |
| Demand may be unmet | nonnegative slack | `served[i] + unmet[i] >= demand[i]` |
| Absolute deviation penalty | nonnegative slack | `actual-target <= dev`, `target-actual <= dev` |
| Inventory balance | inventory variables | `inv[t+1] = inv[t] + inbound - outbound` |
| Station/storage upper bound | inventory variable | `inv[i,t] <= capacity[i]` |
| Cannot remove unavailable stock | move variable | `outbound[i,t] <= inv[i,t]` |
| Vehicle starts at depot | arc variables | `sum_j x[v, START, j] == use_vehicle[v]` |
| Vehicle ends at depot | arc variables | `sum_i x[v, i, END] == use_vehicle[v]` |
| Route continuity | arc variables | `incoming[v,i] == outgoing[v,i]` |
| Visit at most once | arc variables | `outgoing[v,i] <= 1` |
| Split service allowed | arc/quantity variables | omit global single-visit; aggregate quantities over resources |
| Time window | arrival variable | `earliest[i] <= arrival[v,i] <= latest[i]` when visited |
| Travel time propagation | arc + arrival | `arrival[j] >= arrival[i] + service_time[i] + travel[i,j] - M(1-x[i,j])` |
| Precedence | start/arrival variables | `start[b] >= finish[a]` |
| Route duration limit | arc variables | `sum travel[i,j] * x[v,i,j] <= max_duration[v]` |

## Constraint Examples

### Capacity

```python
for r in resources:
    model.addCons(quicksum(amount[i, r] for i in items) <= capacity[r])
```

### Quantity Allowed Only When Active

Use the tightest possible `M`.

```python
for i in items:
    model.addCons(quantity[i] <= upper_bound[i] * use[i])
```

### Soft Demand Satisfaction



**Bike rebalancing note:** station unmet is typically an absolute deviation between target net change and achieved net change. Prefer modeling via `pos[i], neg[i]` with `unmet[i] = pos[i] + neg[i]` (see the bike-rebalancing section) to match `abs()` exactly while staying linear.
```python
unmet = {i: model.addVar(vtype="I", lb=0, name=f"unmet_{i}") for i in customers}

for i in customers:
    model.addCons(served[i] + unmet[i] >= demand[i])

penalty_cost = quicksum(penalty[i] * unmet[i] for i in customers)
```

### Absolute Target Deviation

Never use Python `abs()` on solver expressions.

```python
dev = {i: model.addVar(vtype="C", lb=0, name=f"dev_{i}") for i in items}

for i in items:
    model.addCons(actual[i] - target[i] <= dev[i])
    model.addCons(target[i] - actual[i] <= dev[i])
```

### Depot Start and End

If every vehicle must be used:

```python
for v in vehicles:
    model.addCons(quicksum(x[v, START, j] for j in locations) == 1)
    model.addCons(quicksum(x[v, i, END] for i in locations) == 1)
```

If vehicles are optional:

```python
use_vehicle = {v: model.addVar(vtype="B", name=f"use_vehicle_{v}") for v in vehicles}

for v in vehicles:
    model.addCons(quicksum(x[v, START, j] for j in locations) == use_vehicle[v])
    model.addCons(quicksum(x[v, i, END] for i in locations) == use_vehicle[v])
```

### Route Continuity and At-Most-Once Visits

```python
for v in vehicles:
    for i in locations:
        incoming = quicksum(x[v, j, i] for j in from_nodes if j != i)
        outgoing = quicksum(x[v, i, j] for j in to_nodes if j != i)

        model.addCons(incoming == outgoing)
        model.addCons(outgoing <= 1)
```

This means vehicle `v` visits location `i` no more than once. It does not prevent a different vehicle from also visiting `i`.

### Global Single-Visit Rule

Use only when the real rule forbids split service across vehicles/resources.

```python
for i in locations:
    model.addCons(
        quicksum(x[v, i, j] for v in vehicles for j in to_nodes if j != i) <= 1
    )
```

Do not add this rule when a large pickup/dropoff target may need multiple vehicles.

### Load or State Transition Along Selected Arcs



**Strength tip (IRP/bike rebalancing):** if `change_at_j` is itself a decision (pickup/dropoff), bound it as tightly as possible using station data (available bikes / free space) and link it to a visit binary. Then choose `M` from those bounds, not a generic multiple of `vehicle_capacity`.

A common weak point is using a single global `M = 2*vehicle_capacity` (or larger). Prefer per-node or per-arc bounds:
- `service[v,j] in [-free_space[j], initial_bikes[j]]`
- `load[v,i] in [0, Q]`
So a safe tighter constant is `M_j = Q + max(initial_bikes[j], free_space[j])`, and use `M(i,j)=M_j`.
If `state[j] = state[i] + change[j]` when arc `(i, j)` is used:

```python
M = 2 * vehicle_capacity

for v in vehicles:
    for i, j in arcs:
        change_at_j = service[v, j] if isinstance(j, int) else 0
        model.addCons(load[v, j] - load[v, i] - change_at_j <= M * (1 - x[v, i, j]))
        model.addCons(load[v, j] - load[v, i] - change_at_j >= -M * (1 - x[v, i, j]))
```

This pattern works for load, arrival time, battery charge, inventory state, and other route-dependent state variables. Pick `M` from real variable bounds.

### Time Windows

```python
for v in vehicles:
    for i in locations:
        visit_i = quicksum(x[v, i, j] for j in to_nodes if j != i)
        model.addCons(arrival[v, i] >= earliest[i] - horizon * (1 - visit_i))
        model.addCons(arrival[v, i] <= latest[i] + horizon * (1 - visit_i))

    for i, j in arcs:
        if j in locations:
            model.addCons(
                arrival[v, j] >= arrival[v, i] + service_time.get(i, 0) + travel_time[i, j] - horizon * (1 - x[v, i, j])
            )
```

## Inventory Pickup/Dropoff Pattern



## Bike Rebalancing / Inventory-Routing: Strong Formulations (Incumbent Quality)

Bike rebalancing is an **inventory-routing problem (IRP)**: routing decisions (arcs/visits) must be tightly linked to **station service quantities** and **vehicle load propagation**. A model can be logically correct but still too weak, leading to poor incumbents under time limits.

### 1) Prefer split pickup/drop variables over a single signed service (stronger linking)

Single signed variables are compact but often looser. A stronger pattern is:
- `p[v,i] >= 0` bikes picked up at station `i` by vehicle `v`
- `d[v,i] >= 0` bikes dropped off at station `i` by vehicle `v`
- optional binary `y[v,i]` = vehicle `v` visits station `i`
- optional binary `z[v,i]` = 1 if pickup at `i` (and 0 implies dropoff) to enforce “not both”

Link quantities tightly to visits with **station-specific bounds** (avoid generic `vehicle_capacity` when tighter bounds exist):

- Pickup is limited by available bikes: `p[v,i] <= initial_bikes[i] * y[v,i]`
- Dropoff is limited by free space: `d[v,i] <= (station_capacity[i] - initial_bikes[i]) * y[v,i]`
- Vehicle capacity can also bound each stop: `p[v,i] <= vehicle_capacity * y[v,i]`, `d[v,i] <= vehicle_capacity * y[v,i]` (redundant but can help)

Enforce “at a single stop, do not both pick up and drop off”:

- `p[v,i] <= initial_bikes[i] * z[v,i]`
- `d[v,i] <= (station_capacity[i] - initial_bikes[i]) * (1 - z[v,i])`
- `z[v,i] <= y[v,i]` (or `z[v,i] <= y[v,i]` and `y[v,i]` implied by route)

If you do keep a signed `service[v,i]`, still add tight bounds using station data:
- `service[v,i] <= initial_bikes[i] * y[v,i]`
- `-service[v,i] <= (station_capacity[i] - initial_bikes[i]) * y[v,i]`

### 2) Stronger vehicle load propagation (avoid loose big-M)

Use explicit load after each visited node and propagate along arcs:
- `L[v,i]` = load after servicing node `i` (or upon arrival; be consistent)

For split variables with service `s[v,i] = p[v,i] - d[v,i]`:

For every arc `(i,j)` used by vehicle `v`:
- `L[v,j] >= L[v,i] + s[v,j] - M(i,j) * (1 - x[v,i,j])`
- `L[v,j] <= L[v,i] + s[v,j] + M(i,j) * (1 - x[v,i,j])`

Pick **tight M**. A safe generic bound is `M = vehicle_capacity`, but you can do better:
- Since `L` is in `[0, Q]` and `s[v,j]` is in `[-free_space[j], initial_bikes[j]]`, use `M(i,j) = Q + max(initial_bikes[j], free_space[j])` (often much smaller than global constants).

Initialize and terminate load consistently:
- If `START` is a node: set `L[v,START] = start_load[v]`.
- If start load is a decision: `0 <= start_load[v] <= Q` and link to first stop via arc constraints.
- End load: either `L[v,END] = end_load[v]` or compute from last visited node.

### 3) Unmet target as absolute deviation using +/− slacks (numerically stable)

Targets are station net changes:
- Station net change (pickup minus dropoff): `net[i] = sum_v (p[v,i] - d[v,i])`

Model unmet amount via positive/negative deviation:
- `net[i] - target[i] = pos[i] - neg[i]`
- `pos[i] >= 0, neg[i] >= 0`
- `unmet[i] = pos[i] + neg[i]`

This is equivalent to `abs(target-net)` but often stronger than a single `dev` plus two inequalities when combined with other bounds.

### 4) Valid inequalities / global feasibility checks (tighten early)

Add global bounds that cut impossible service plans before routing is decided:

Let `Pmax_i = initial_bikes[i]` and `Dmax_i = station_capacity[i] - initial_bikes[i]`.
Then for each station:
- `net[i] <= Pmax_i` and `net[i] >= -Dmax_i` (already implied by linking, but keep as aggregate cuts)

Fleet capacity across the whole plan:
- Total pickup cannot exceed total dropoff plus total start-load plus total free capacity along the route; a simple conservative cut:
  - `sum_{i,v} p[v,i] <= sum_{i,v} d[v,i] + sum_v start_load[v] + vehicle_count * Q`
  (adjust if vehicles must return with any load; this is a modeling choice)

If each vehicle must visit at least one station:
- `sum_{j in locations} x[v,START,j] == 1` (or `>= 1`) rather than allowing `0`.

### 5) Objective scaling: travel vs unmet penalty

When penalty is large, the solver should prioritize eliminating unmet bikes, but if the formulation is weak it may still get stuck. Recommendations:
- Keep `penalty_weight` directly on `unmet[i]` (integers if bike counts are integers).
- Avoid fractional service variables if bikes must be integral.
- If needed, use a lexicographic solve: (1) minimize total unmet, then (2) minimize travel with unmet fixed/upper bounded (implement via two solves or a big weight).

### 6) Formulation strength impacts performance

Under fixed time limits, stronger linking + tighter M values usually improves incumbent quality dramatically:
- tighter service bounds shrink the LP relaxation
- tighter load propagation reduces symmetric/degenerate solutions
- explicit pos/neg deviation helps branching on unmet structure
For rebalancing or material movement, define one signed service variable. Recommended convention:

- `service[v, i] > 0`: pickup from location `i`, vehicle load increases, location inventory decreases.
- `service[v, i] < 0`: dropoff to location `i`, vehicle load decreases, location inventory increases.

```python
service = {
    (v, i): model.addVar(vtype="I", lb=-vehicle_capacity, ub=vehicle_capacity, name=f"service_{v}_{i}")
    for v in vehicles
    for i in locations
}

for v in vehicles:
    for i in locations:
        visit_i = quicksum(x[v, i, j] for j in to_nodes if j != i)
        model.addCons(service[v, i] <= vehicle_capacity * visit_i)
        model.addCons(service[v, i] >= -vehicle_capacity * visit_i)

for i in locations:
    net_change = quicksum(service[v, i] for v in vehicles)
    free_space = storage_capacity[i] - initial_inventory[i]

    model.addCons(net_change <= initial_inventory[i])  # pickup cannot exceed stock
    model.addCons(net_change >= -free_space)           # dropoff cannot exceed space
```

If the target is a desired net pickup/dropoff:

```python
unmet = {i: model.addVar(vtype="I", lb=0, name=f"unmet_{i}") for i in locations}

for i in locations:
    net_change = quicksum(service[v, i] for v in vehicles)
    model.addCons(net_change - target[i] <= unmet[i])
    model.addCons(target[i] - net_change <= unmet[i])
```

Extract pickup/dropoff output as:

```python
picked_up = max(service_value, 0)
dropped_off = max(-service_value, 0)
```

## Objective Assembly



**Performance note:** If the solver returns feasible but slightly subpar solutions under a time limit, it is often a formulation-strength issue rather than a coding bug. Tighten linking bounds, tighten big-M, and consider a two-stage objective (min unmet first, then travel) when penalty dominates.
Build named components:

```python
travel_cost = quicksum(distance[i, j] * x[v, i, j] for v in vehicles for i, j in arcs)
fixed_cost = quicksum(vehicle_fixed_cost[v] * use_vehicle[v] for v in vehicles)
penalty_cost = quicksum(penalty[i] * unmet[i] for i in customers)

model.setObjective(travel_cost + fixed_cost + penalty_cost, "minimize")
```
