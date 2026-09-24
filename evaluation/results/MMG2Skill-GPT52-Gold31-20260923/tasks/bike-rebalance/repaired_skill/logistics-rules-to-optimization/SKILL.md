---
name: logistics-rules-to-optimization
description: Translate rebalancing business rules (routing + pickup/dropoff + inventory
  + unmet-target penalty) into a consistent MIP formulation and extract a reportable
  solution.
---

## Steps
1. Enumerate entities and sets: vehicles `K`, stations `N`, depot start/end nodes, and routing arcs.
2. Choose variables consistent with the rules:
   - `x[v,i,j] ∈ {0,1}` for route arcs
   - `service[v,i] ∈ Z` (signed): `>0` pickup, `<0` dropoff, `=0` no service
   - `load[v,node] ∈ Z` bounded in `[0, vehicle_capacity]`
   - `unmet[i] ≥ 0` for absolute deviation from station `net_rebalancing_target`
3. Add routing feasibility constraints:
   - each vehicle leaves `depot_start` once and enters `depot_end` once (vehicles must be used)
   - continuity at each station: in-degree = out-degree per vehicle
   - per-vehicle “visit at most once”: out-degree at a station ≤ 1
4. Link service to visiting and enforce “no pickup and drop at the same stop” by using a *single signed* `service[v,i]` and bounding it to zero when not visited:
   - `-cap * visit[v,i] ≤ service[v,i] ≤ cap * visit[v,i]`
5. Enforce load propagation along selected arcs with big‑M:
   - `load[v,j] = load[v,i] + service[v,j]` when arc `(i→j)` is used (treat depot change as 0)
   - keep all loads within `[0, vehicle_capacity]`, including start and end loads
6. Enforce station inventory feasibility (hard bounds), using aggregated station net change:
   - `net_change[i] = Σ_v service[v,i]`
   - pickup limit: `net_change[i] ≤ initial_bikes[i]`
   - dropoff limit: `net_change[i] ≥ -(station_capacity[i] - initial_bikes[i])`
   These bounds correctly handle structurally impossible targets (e.g., pickup target exceeding available bikes) by limiting achievable service.
7. Model unmet rebalancing with absolute deviation linearization:
   - `net_change[i] - target[i] ≤ unmet[i]`
   - `target[i] - net_change[i] ≤ unmet[i]`
   - penalty term: `penalty_weight * Σ_i unmet[i]`
8. Objective: minimize `total_travel_distance + unmet_penalty`.
9. Extract a reportable solution:
   - reconstruct each vehicle’s ordered route from selected arcs (and ensure it is a single depot→…→depot path)
   - per stop, output either `bikes_picked_up=max(service,0)` or `bikes_dropped_off=max(-service,0)`, and compute `load_after_stop`
   - station section must include **every station** with totals, `net_bike_change`, and `unmet_rebalancing_amount = abs(target - net_bike_change)`.
## Expected Result
A solution that satisfies all hard routing/load/inventory rules, allows unavoidable target shortfalls via `unmet` penalties when targets exceed physical bounds, and supports direct construction of the required `report.json` station/vehicle summaries.
