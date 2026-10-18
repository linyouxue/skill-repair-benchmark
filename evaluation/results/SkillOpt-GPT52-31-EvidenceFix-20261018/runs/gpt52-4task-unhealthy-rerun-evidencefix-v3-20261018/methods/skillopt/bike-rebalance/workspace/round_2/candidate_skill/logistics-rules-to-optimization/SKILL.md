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
| Quantity only if selected (use tight, data-driven M) | `q[i]`, `use[i]` | `q[i] <= upper_bound[i] * use[i]` (avoid generic big-M) |
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

If `state[j] = state[i] + change[j]` when arc `(i, j)` is used:


**Formulation strengthening tips (critical for runtime + solution quality)**

- **Tighten big-M aggressively** using real bounds:
  - For load transitions, M can often be `max_Δ = max_pickup_at_node + max_dropoff_at_node` or simply `Q`, not `2Q`.
  - If using `pu/do`, then `|load[j]-load[i]| ≤ ub_pu[j] + ub_do[j]`.
- **Bind quantities to station-specific bounds**, not vehicle capacity:
  - `pu[v,i] ≤ inv0[i]*visit[v,i]` and `do[v,i] ≤ (cap[i]-inv0[i])*visit[v,i]` are much tighter than `Q*visit`.
- **Do not decouple vehicles greedily** when the objective includes unmet-target penalties:
  - Net service decisions at one station interact with feasibility and penalties at others through vehicle capacities and route structure. Model all vehicles jointly.
- **Avoid weak “visit implies service” only via loose bounds**:
  - If a station is visited, the model may still choose zero service; that’s fine. But if service occurs, it must imply a visit (e.g., `pu[v,i] ≤ ub*visit[v,i]`, `do[v,i] ≤ ub*visit[v,i]`).
- **Use split-service deliberately**:
  - Allow multiple vehicles to serve the same station unless explicitly forbidden. The “at most once per vehicle” rule does not imply “globally once”.
- **Incumbent-first decomposition (optional, practical)**:
  1) Solve a fast relaxation/LP or small MIP to decide approximate `net[i]` (how much to pick/drop at each station) subject to global stock/space and vehicle capacity totals.
  2) Build initial routes that realize those net moves (e.g., cluster surpluses/deficits, greedy insertion).
  3) Warm-start the integrated IRP MIP with that incumbent and re-optimize.

These steps often close small benchmark gaps when time-limited.
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

For rebalancing or material movement, define one signed service variable. Recommended convention:

- `service[v, i] > 0`: pickup from location `i`, vehicle load increases, location inventory decreases.
- `service[v, i] < 0`: dropoff to location `i`, vehicle load decreases, location inventory increases.


### Bike / Station Rebalancing = Integrated Inventory-Routing Pattern (IRP)



#### Bike-rebalancing constraint template (copy/paste checklist)

**Define sign conventions up front (avoid silent sign flips):**
- `pu[v,i] ≥ 0` = bikes picked up by vehicle `v` at station `i` (station inventory decreases, vehicle load increases)
- `do[v,i] ≥ 0` = bikes dropped off by vehicle `v` at station `i` (station inventory increases, vehicle load decreases)
- Station-level totals: `PU[i] = Σ_v pu[v,i]`, `DO[i] = Σ_v do[v,i]`
- Station net change (per task spec): `net[i] = PU[i] - DO[i]` (positive means removed from station)
- Final inventory: `inv_final[i] = inv0[i] - PU[i] + DO[i]`

**Hard station inventory constraints (must-have):**
- Inventory conservation: `inv_final[i] = inv0[i] - Σ_v pu[v,i] + Σ_v do[v,i]`
- Bounds: `0 ≤ inv_final[i] ≤ cap[i]`
  - Equivalent aggregated bounds (often useful as redundant constraints):
    - `Σ_v pu[v,i] ≤ inv0[i]`
    - `Σ_v do[v,i] ≤ cap[i] - inv0[i]`

**Link quantities to visit decisions (prevent “teleporting service”):**
Let `visit[v,i] ∈ {0,1}` indicate vehicle `v` visits station `i`.
- `pu[v,i] ≤ inv0[i] * visit[v,i]`
- `do[v,i] ≤ (cap[i] - inv0[i]) * visit[v,i]`

**Mutual exclusivity at a stop (if rule says no both pickup and dropoff):**
Introduce `y[v,i] ∈ {0,1}` where `y=1` means pickup-mode.
- `pu[v,i] ≤ inv0[i] * y[v,i]`
- `do[v,i] ≤ (cap[i] - inv0[i]) * (1 - y[v,i])`
- Strengthening: `y[v,i] ≤ visit[v,i]`

**Unmet targets as explicit slack (keeps feasibility without illegal moves):**
Given target `tgt[i]` on `net[i] = PU[i] - DO[i]`, model absolute deviation with two slacks:
- `net[i] - tgt[i] = u_pos[i] - u_neg[i]`
- `u_pos[i] ≥ 0`, `u_neg[i] ≥ 0`
- Objective penalty term: `penalty_weight * Σ_i (u_pos[i] + u_neg[i])`

(Equivalent form: `net[i]-tgt[i] ≤ unmet[i]` and `tgt[i]-net[i] ≤ unmet[i]`, `unmet[i] ≥ 0`.)
When a problem couples **routing** (which stations are visited, in what order) with **inventory rebalancing** (how many units picked up/dropped off at each station), model it as an integrated IRP, not as a loose “route then adjust” rule-of-thumb.

**Core variables** (single time period, nightly rebalance):
- Route arcs: `x[v,i,j] ∈ {0,1}`
- Visit indicator: `visit[v,i] ∈ {0,1}` (optional but convenient)
- Pickup / dropoff amounts (nonnegative, avoids sign confusion):
  - `pu[v,i] ≥ 0` bikes picked up by vehicle `v` at station `i`
  - `do[v,i] ≥ 0` bikes dropped off by vehicle `v` at station `i`
  - Enforce “not both at same stop” via a mode binary `y[v,i] ∈ {0,1}` if needed
- Vehicle load after servicing node `i`: `load[v,i] ∈ [0, Q]`
- Station final inventory: `inv_final[i] ∈ [0, cap[i]]`
- Unmet target absolute deviation: `unmet[i] ≥ 0`

**Station inventory balance and targets**



**Common failure modes (bike rebalancing):**
- **Over-pick:** `Σ_v pu[v,i] > inv0[i]` (or `inv_final[i] < 0`) because inventory bounds were omitted or sign was flipped.
- **Over-fill:** `Σ_v do[v,i] > cap[i]-inv0[i]` (or `inv_final[i] > cap[i]`).
- **Net-change sign mistake:** treating `net = dropoff - pickup` while penalty compares to `tgt` defined as `pickup - dropoff`.
- **Aggregating per-stop actions incorrectly:** station totals not equal to sum of vehicle stop quantities.
- **Service without a visit:** missing `pu/do ≤ M*visit` allows nonzero quantities at unvisited stations.
- **Illegal both pick and drop at same stop:** missing (or incorrectly indexed) mutual exclusivity `y[v,i]` constraints.
Let station net change be `net[i] = Σ_v (pu[v,i] - do[v,i])` (positive means removed from station).

- Final inventory (single period):
  - `inv_final[i] = inv0[i] - Σ_v pu[v,i] + Σ_v do[v,i]`
  - `0 ≤ inv_final[i] ≤ cap[i]`
- Absolute deviation from rebalancing target `tgt[i]`:
  - `net[i] - tgt[i] ≤ unmet[i]`
  - `tgt[i] - net[i] ≤ unmet[i]`

**Vehicle load propagation (coupled to route order)**

If `load[v,i]` is the load after servicing node `i` (and depot is a node too), then along each selected arc `(i,j)`:
- `load[v,j] = load[v,i] + pu[v,j] - do[v,j]` when `x[v,i,j]=1`
- Implement with tight big-M using known bounds (see strengthening tips below).

Also enforce load bounds at every node: `0 ≤ load[v,i] ≤ Q`.

**Strong linking between visit and allowed quantities (avoid loose formulations)**

Use **tight, data-driven upper bounds** instead of generic `Q` when possible:
- Station pickup cannot exceed available bikes:
  - `Σ_v pu[v,i] ≤ inv0[i]`
- Station dropoff cannot exceed free space:
  - `Σ_v do[v,i] ≤ cap[i] - inv0[i]`

Per-vehicle/per-visit linking:
- `pu[v,i] ≤ ub_pu[i] * visit[v,i]`, where `ub_pu[i] = inv0[i]`
- `do[v,i] ≤ ub_do[i] * visit[v,i]`, where `ub_do[i] = cap[i] - inv0[i]`

“No pickup and dropoff at the same stop”:
- Introduce `y[v,i] ∈ {0,1}` where `y=1` means pickup-mode.
- `pu[v,i] ≤ ub_pu[i] * y[v,i]`
- `do[v,i] ≤ ub_do[i] * (1 - y[v,i])`
- Also link mode to visit: `y[v,i] ≤ visit[v,i]` (optional but strengthens relaxation)

**Objective (travel + unmet penalty)**
- `min Σ_{v,i,j} dist[i,j]*x[v,i,j] + penalty_weight * Σ_i unmet[i]`

This matches bike-sharing scoring where each unit of unmet target incurs a penalty.
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
    # If using a signed service variable, DO NOT rely on net_change bounds alone.
    # Always encode final inventory bounds to prevent over-pick / over-fill.
    net_change = quicksum(service[v, i] for v in vehicles)  # + = pickup, - = dropoff

    inv_final_i = model.addVar(vtype="I", lb=0, ub=storage_capacity[i], name=f"inv_final_{i}")
    model.addCons(inv_final_i == initial_inventory[i] - quicksum(max(service[v, i], 0) for v in vehicles) + quicksum(max(-service[v, i], 0) for v in vehicles))

    # Prefer the pu/do nonnegative formulation when you need these constraints cleanly.
    # If you keep signed service, add explicit pu/do split variables (pu, do >= 0) with service = pu - do,
    # then enforce: sum_v pu[v,i] <= initial_inventory[i] and sum_v do[v,i] <= storage_capacity[i]-initial_inventory[i].
```


**Prefer disaggregated pickup/dropoff variables when you must enforce “no both”**



**Implementation note (avoid non-linear `max()` in constraints):**
If you need hard inventory bounds, do not write `max(service,0)` in constraints. Instead:
- Introduce `pu[v,i] ≥ 0`, `do[v,i] ≥ 0`
- Add `service[v,i] = pu[v,i] - do[v,i]`
- Then apply linear constraints on `Σ_v pu[v,i]` and `Σ_v do[v,i]` as shown in the template above.
A single signed `service[v,i]` is compact, but it makes the “not both pick up and drop off at a single stop” rule awkward. If that rule is present (as in bike rebalancing), use `pu[v,i]` and `do[v,i]` with a mode binary `y[v,i]` as shown above.

If you keep signed `service[v,i]`, enforce non-simultaneity with split variables:
- `service[v,i] = pu[v,i] - do[v,i]`, `pu,do ≥ 0`
- then apply the mode constraints to `pu/do`.

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

Build named components:

```python
travel_cost = quicksum(distance[i, j] * x[v, i, j] for v in vehicles for i, j in arcs)
fixed_cost = quicksum(vehicle_fixed_cost[v] * use_vehicle[v] for v in vehicles)
penalty_cost = quicksum(penalty[i] * unmet[i] for i in customers)

model.setObjective(travel_cost + fixed_cost + penalty_cost, "minimize")
```
