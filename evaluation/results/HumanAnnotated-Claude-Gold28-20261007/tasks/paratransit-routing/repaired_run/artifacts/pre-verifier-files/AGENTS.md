# Paratransit Dial-A-Ride Instance Notes

- Instance: 252 passengers, 515 trips, 32 vehicles, capacity 3, time window width 30.
- All trips: `pickup_service_time=5`, `dropoff_service_time=5`, `passenger_count=1`.
- Expected arrival times: 330..1410 (minutes after midnight).
- Shift grid: hourly starts 300..840; 8-hour shift; route end <= 1320.
- Matrix has ~2063 negative entries (invalid arcs, ~0.2%); diagonals are -1.
- Node layout per spec:
  - 0 = start depot, 1..n pickups, n+1..2n dropoffs, 2n+1 = end depot.
  - For trip index i (0-based): pickup = 1+i, dropoff = 1+n+i.
- 4 trips have expected_arrival > 1320 or otherwise infeasible windows; their 4 passenger
  sets are entirely unservable → max feasible served trips = 504.

## Solver (`/root/solve.py`)

- OR-Tools RoutingModel with cloned start/end depots per vehicle (32 of each).
- Internal solver nodes: `[0,n)` pickups, `[n,2n)` dropoffs, start copies, end copies.
- Transit matrix = travel_time + from_node_service_time (0 at depot copies).
  Negative travel-time arcs replaced with INVALID=1e6 so the time dimension forbids them.
- Time dimension: slack 480, horizon 1320, `fix_start_cumul_to_zero=False`.
- Capacity dimension: unary +1 at pickups, -1 at dropoffs, 0 depots; capacity 3.
- Pickup-delivery pairs with same-vehicle and precedence constraints.
- CP-style grouped disjunction per passenger set on pickup nodes (max_cardinality=|S|,
  penalty=|S|*100000). Each dropoff gets its own zero-penalty disjunction.
- Vehicle start cumul restricted to the hourly menu via `SetValues`; span <=480.
- Forced-skip trips (whole passenger sets containing an infeasible trip) are marked by
  `ActiveVar.SetValue(0)` on their pickup and dropoff.
- First-solution: PARALLEL_CHEAPEST_INSERTION. Metaheuristic: GUIDED_LOCAL_SEARCH.
  Pass solver time limit as argv[1] in seconds (default 180).

## Postprocessing

- Extract raw route sequences from `NextVar`.
- Compute per-route served trip set (pickups ∩ dropoffs on same vehicle).
- Keep only passenger sets fully served (all-or-none). Partial sets are stripped.
- Replay the filtered route with the solver's `Time.CumulVar(Start)` as `start_time`
  and audit window/load/depot/shift rules from scratch before emitting.

## Verifier (`/root/verify.py`)

- Independent reimplementation of the feasibility rules; recomputes arrivals, loads,
  windows, shift start grid, shift duration, final return time.
- Confirms report has no issues, no partial passenger sets, no double-served trips.

## Last Run Result

- 600s solve: 470 trips served (/504 feasible) across 32 routes, 0 feasibility issues.
- GLS stalled at objective ~3,410,653 for the final 5 minutes.
