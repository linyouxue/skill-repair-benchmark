---
name: routing-subtour-elimination
description: Subtour-elimination methods for TSP, VRP, pickup/dropoff routing, and routing MIPs with binary arc variables. Use when route-continuity constraints may permit disconnected cycles and the model needs MTZ constraints, flow-based connectivity constraints, DFJ subset cuts, or lazy/iterative subtour cuts.
---

# Routing Subtour Elimination

In routing MIPs, degree and continuity constraints are not enough. A vehicle can have one depot-to-depot path and a separate closed cycle among stations. Add subtour-elimination constraints whenever binary arc variables decide routes.

Use this base notation:

```python
START = "depot_start"
END = "depot_end"
vehicles = range(K)
stations = range(n)
from_nodes = [START, *stations]
to_nodes = [*stations, END]
arcs = [(i, j) for i in from_nodes for j in to_nodes if i != j and not (i == START and j == END)]

x = {(v, i, j): model.addVar(vtype="B", name=f"x_{v}_{i}_{j}") for v in vehicles for i, j in arcs}
```

## Required Base Route Constraints (VRP-safe)

Subtour elimination assumes each visited station has matching inbound/outbound arcs **and** that visits are consistent with depot start/end structure.

For multi-vehicle VRP models (including bike rebalancing), avoid forcing every vehicle to run a route unless the task explicitly requires it. Use a binary `use[v]` and tie depot arcs to it, and enforce “visit each station at most once across the fleet” if required.

```python
# vehicle used indicator
use = {v: model.addVar(vtype="B", name=f"use_{v}") for v in vehicles}

# (optional) station visit indicator per vehicle
y = {(v, i): model.addVar(vtype="B", name=f"y_{v}_{i}") for v in vehicles for i in stations}

for v in vehicles:
    # depot start/end: exactly one departure/arrival if vehicle is used
    model.addCons(quicksum(x[v, START, j] for j in stations) == use[v])
    model.addCons(quicksum(x[v, i, END] for i in stations) == use[v])

    for i in stations:
        incoming = quicksum(x[v, j, i] for j in from_nodes if j != i)
        outgoing = quicksum(x[v, i, j] for j in to_nodes if j != i)
        model.addCons(incoming == outgoing)
        model.addCons(outgoing == y[v, i])  # visit iff one outgoing arc

# each station is visited by at most one vehicle (common benchmark rule)
for i in stations:
    model.addCons(quicksum(y[v, i] for v in vehicles) <= 1)

# if the task requires every vehicle to visit >=1 station, enforce it explicitly
# model.addCons(quicksum(y[v, i] for i in stations) >= 1)  # per v
```

The subtour methods below prevent station-only cycles that are disconnected from `START` and ensure each vehicle’s selected arcs form a single connected depot-to-depot path.

## 1. MTZ Order Constraints

MTZ adds an order variable for each vehicle-station pair. If vehicle `v` travels from station `i` to station `j`, then `order[v, j]` must be greater than `order[v, i]`.

```python
order = {
    (v, i): model.addVar(vtype="C", lb=1, ub=max(1, n), name=f"order_{v}_{i}")
    for v in vehicles
    for i in stations
}

for v in vehicles:
    for i in stations:
        for j in stations:
            if i != j:
                model.addCons(order[v, i] - order[v, j] + n * x[v, i, j] <= n - 1)
```

Pros:

- Compact: `O(K n^2)` constraints and `O(K n)` extra variables.
- Easy to implement in common Python optimization APIs.
- Good default for small and medium benchmark instances.

Cons:

- LP relaxation is weak compared with cutset or flow formulations.
- Can be slow for larger VRPs.
- Order variables are artificial; do not interpret them as service times unless you also model time.

Use MTZ first when correctness and implementation speed matter more than best possible MIP strength.



### MTZ Strengthening Tips

Weak MTZ formulations can noticeably slow SCIP on VRP-style benchmarks even when the final incumbent has no subtours.

Tighten MTZ with additional structure:

```python
# activate order only if station is visited
for v in vehicles:
    for i in stations:
        visit_i = quicksum(x[v, i, j] for j in to_nodes if j != i)
        model.addCons(order[v, i] >= visit_i)
        model.addCons(order[v, i] <= n * visit_i)
```

Also tighten depot connectivity:

```python
# if a vehicle is used, force at least one station-to-station move
for v in vehicles:
    model.addCons(
        quicksum(x[v, i, j] for i in stations for j in stations if i != j)
        >=
        quicksum(x[v, START, j] for j in stations) - 1
    )
```

Use tighter big-M values whenever route-length bounds or maximum stops per vehicle are known. Avoid unnecessarily large `n` constants.
## 2. Single-Commodity Flow Connectivity

Add an artificial connectivity flow that starts at the depot and sends one unit to every visited station. This flow is not physical vehicle load.

```python
visit = {
    (v, i): quicksum(x[v, i, j] for j in to_nodes if j != i)
    for v in vehicles
    for i in stations
}

flow_arcs = [(i, j) for i in [START, *stations] for j in stations if i != j]
f = {
    (v, i, j): model.addVar(vtype="C", lb=0, ub=n, name=f"conn_flow_{v}_{i}_{j}")
    for v in vehicles
    for i, j in flow_arcs
}

for v in vehicles:
    total_visits = quicksum(visit[v, i] for i in stations)
    model.addCons(quicksum(f[v, START, j] for j in stations) == total_visits)

    for i, j in flow_arcs:
        model.addCons(f[v, i, j] <= n * x[v, i, j])

    for i in stations:
        incoming_flow = quicksum(f[v, h, i] for h in [START, *stations] if h != i)
        outgoing_flow = quicksum(f[v, i, j] for j in stations if j != i)
        model.addCons(incoming_flow - outgoing_flow == visit[v, i])
```

Pros:

- Stronger connectivity logic than MTZ in many models.
- Static constraints, no callback needed.
- Works with optional station visits.

Cons:

- Adds `O(K n^2)` continuous variables.
- Do not reuse truck load as the connectivity flow when the vehicle can both pick up and drop off. Physical load can increase and decrease; connectivity flow should monotonically distribute artificial units.
- More memory than MTZ.

Use this when MTZ gives weak incumbents or slow progress and the instance is still modest in size.



### Connectivity strength and incumbent quality (benchmark-gated tasks)

In benchmark-gated VRPs, a model can be **feasible** yet still produce a worse incumbent because the LP relaxation allows many disconnected or weakly connected fractional patterns. Strengthening connectivity (flow-based formulations or DFJ/lazy SECs) often improves *incumbent quality under time limits* by guiding the search toward single-route structures earlier.

Practical guidance:

- Prefer **single-commodity flow** (or multi-commodity only when `n` is tiny) over bare MTZ when you need better incumbents quickly.
- If your solver supports it, use **lazy subtour cuts** (SEC separation) to keep the model small but strong.
- Always ensure the *base VRP structure* is correct (vehicle-use, depot start/end, and station single-visit rules). Subtour cuts cannot fix a wrong base model.


Single-commodity flow is often a better default than MTZ for medium-size VRPs when objective quality under time limits matters more than raw model size. The stronger LP relaxation frequently improves incumbent discovery and reduces disconnected partial-route artifacts during search.

If memory allows, prefer flow connectivity over bare MTZ when:

- vehicles are interchangeable and many route combinations exist
- pickup/dropoff balance constraints already make the model hard
- SCIP spends substantial time proving connectivity
- small incumbent-quality improvements matter
## 3. DFJ Subset Cuts

For every nonempty proper subset `S` of stations, selected station-to-station arcs inside `S` cannot form a closed cycle:

```text
sum_{i in S, j in S, i != j} x[v,i,j] <= |S| - 1
```

For very small `n`, static enumeration is possible:

```python
from itertools import combinations

for v in vehicles:
    for r in range(2, n):
        for S_tuple in combinations(stations, r):
            S = set(S_tuple)
            model.addCons(
                quicksum(x[v, i, j] for i in S for j in S if i != j) <= len(S) - 1
            )
```

Pros:

- Strong, direct subtour elimination.
- No artificial order or flow variables.

Cons:

- Exponential number of constraints.
- Static enumeration is only acceptable for small station counts.

Use static DFJ only for tiny instances or as a debugging baseline.

## 4. Lazy or Iterative Cut Separation

The strongest practical pattern is to solve with base route constraints, detect subtours in incumbents, add only the violated DFJ cuts, and continue.

In solvers with convenient lazy callbacks, add cuts during branch-and-bound. Some Python solver APIs require callback or constraint-handler plumbing for true lazy enforcement, so iterative cut separation is often simpler for portable benchmark code:

```python
def selected_arcs(model, x, v, arcs):
    return [(i, j) for i, j in arcs if model.getVal(x[v, i, j]) > 0.5]


def station_cycles_without_start(selected, stations):
    succ = {i: j for i, j in selected}
    cycles = []
    seen = set()

    for start in stations:
        if start in seen or start not in succ:
            continue
        path = []
        cur = start
        pos = {}
        while cur in succ and cur not in pos and cur not in seen:
            pos[cur] = len(path)
            path.append(cur)
            cur = succ[cur]
        seen.update(path)
        if cur in pos:
            cycle = path[pos[cur]:]
            if START not in cycle and END not in cycle:
                cycles.append(cycle)
    return cycles


while True:
    model.optimize()
    if model.getNSols() == 0:
        raise RuntimeError(f"no feasible solution; status={model.getStatus()}")

    cuts_added = 0
    for v in vehicles:
        selected = selected_arcs(model, x, v, arcs)
        for cycle in station_cycles_without_start(selected, stations):
            if len(cycle) >= 2:
                S = set(cycle)
                model.freeTransform()
                model.addCons(
                    quicksum(x[v, i, j] for i in S for j in S if i != j) <= len(S) - 1
                )
                cuts_added += 1

    if cuts_added == 0:
        break
```

Pros:

- Adds only cuts that are needed.
- Often stronger than MTZ.
- Avoids exponential static SEC generation.

Cons:

- Iterative resolve can be slower than a true callback.
- Requires reliable subtour detection.
- More moving parts than MTZ.

Use this when static MTZ is too weak and the solver environment does not make lazy callbacks convenient.



## Symmetry Breaking for Identical Vehicles

Identical vehicles create many equivalent depot-to-route assignments. Add light symmetry breaking to reduce branch-and-bound duplication.

Example: enforce nondecreasing first visited station IDs.

```python
first_visit = {}
for v in vehicles:
    first_visit[v] = model.addVar(vtype="I", lb=0, ub=n, name=f"first_{v}")

    model.addCons(
        first_visit[v] == quicksum(
            j * x[v, START, j] for j in stations
        )
    )

for v in vehicles[:-1]:
    model.addCons(first_visit[v] <= first_visit[v + 1])
```

Other simple symmetry breakers:

- require lower-index vehicles to be used before higher-index vehicles
- cap unused vehicles to appear only at the end of the fleet ordering
- fix one canonical vehicle to serve the smallest-index mandatory station
## Method Choice

| Method | Best For | Avoid When |
| --- | --- | --- |
| MTZ | Quick, compact, small/medium MIPs | Large hard VRPs where relaxation strength matters |
| Single-commodity flow | Stronger static connectivity, optional visits | Memory is tight, or `n` is large |
| Multi-commodity flow | Very strong small routing models | Most practical benchmark tasks; too many variables |
| Static DFJ | Tiny instances, debugging | More than roughly 15-18 stations without careful filtering |
| Lazy/iterative DFJ cuts | Strong routing models with many possible SECs | Solver API/callback complexity is too risky |

For pickup/dropoff rebalancing, start with MTZ or artificial connectivity flow. Do not use physical truck load as the only subtour-elimination mechanism because pickup/dropoff load can increase and decrease and may not prove route connectivity.

## Validation



### Route-extraction checks (single connected depot-to-depot path)

After solving, validate that each used vehicle has exactly one outgoing arc from `START`, exactly one incoming arc to `END`, and that following successors from `START` reaches `END` without repeats. Also validate that each station has **at most one** predecessor/successor across the route and (if required) is visited by **at most one vehicle** overall.
After solving, reconstruct each route by following selected arcs:

```python
def extract_route(selected):
    outgoing = dict(selected)
    route = [START]
    cur = START
    seen = {START}
    while cur != END:
        if cur not in outgoing:
            raise RuntimeError(f"route disconnected at {cur!r}")
        cur = outgoing[cur]
        if cur in seen and cur != END:
            raise RuntimeError(f"cycle detected at {cur!r}")
        route.append(cur)
        seen.add(cur)
    return route
```

Fail fast if a selected solution has a disconnected cycle, repeated station, missing depot start, or missing depot end.



Additional VRP-specific validation snippets:

```python
def extract_selected_successor(model, x, v, nodes_out):
    succ = {}
    for i in nodes_out:
        cand = [j for j in to_nodes if j != i and (v, i, j) in x and model.getVal(x[v, i, j]) > 0.5]
        if len(cand) > 1:
            raise RuntimeError(f"multiple successors from {i!r} for vehicle {v}")
        if len(cand) == 1:
            succ[i] = cand[0]
    return succ

# check each vehicle is either unused (no arcs) or a single START->...->END chain
for v in vehicles:
    out_start = sum(model.getVal(x[v, START, j]) > 0.5 for j in stations)
    in_end = sum(model.getVal(x[v, i, END]) > 0.5 for i in stations)
    if out_start != in_end:
        raise RuntimeError(f"vehicle {v}: depot start/end mismatch")

# if the benchmark requires global single-visit, verify it post-solve too
visited_by = {i: [] for i in stations}
for v in vehicles:
    for i in stations:
        if sum(model.getVal(x[v, i, j]) > 0.5 for j in to_nodes if j != i) > 0:
            visited_by[i].append(v)
for i, vs in visited_by.items():
    if len(vs) > 1:
        raise RuntimeError(f"station {i} visited by multiple vehicles: {vs}")
```

## Arc Pruning and Routing Preprocessing

Reducing the arc set can improve both incumbent quality and solve time.

Before building routing variables:

- remove self-loops and obviously dominated arcs
- remove arcs that are much longer than a depot-mediated alternative
- restrict each station to its nearest `k` candidate successors when geography is dense
- remove arcs that can never satisfy load or inventory feasibility
- precompute unreachable transitions caused by capacity bounds or mandatory pickup/dropoff direction

Example dominated-arc filter:

```python
candidate_arcs = []
for i, j in arcs:
    direct = dist[i, j]

    # if routing through depot is nearly always cheaper, prune direct move
    via_depot = dist[i, END] + dist[START, j]

    if direct <= 1.5 * via_depot:
        candidate_arcs.append((i, j))
```

Aggressive pruning can remove optimal routes, so keep filters conservative unless exact optimality is not required.
