# SKILL.md

## When to use
Use this skill when you must produce a **nightly bike-rebalancing plan** from a provided `data.json`, deciding:
- **Routes** for multiple vehicles that **start at the depot and end at the depot**
- **Pick-up / drop-off quantities** at visited stations
- A `report.json` that includes **per-vehicle** and **per-station** accounting, plus an overall objective:  
  **total great-circle travel distance (miles) + penalty_weight × total unmet rebalancing amount**.

Before acting, gather evidence from `data.json`:
- `vehicle_count`, `vehicle_capacity`, `penalty_weight`
- depot coordinates and station list with: `station_id`, `latitude`, `longitude`, `initial_bikes`, `station_capacity`, `net_rebalancing_target`
- any declared coordinate schema and required distance metric statement (you must use **great-circle distance with Earth radius 3960.0 miles**)

## Possible Failure Modes
- **Distance mismatch**: using Euclidean distance, wrong Earth radius, swapped lat/lon, degrees not converted to radians, or rounding inconsistently → evaluator rejects `travel_distance_miles`.
- **Route rule violations**:
  - vehicle does not start at depot and end at depot (missing `depot_start` / `depot_end`)
  - vehicle visits a station more than once
  - vehicle has an empty route (stays at depot), which is forbidden
- **Load accounting errors**:
  - `load_after_stop` not equal to `previous_load + picked_up - dropped_off`
  - `start_load`, `load_after_stop`, or `end_load` outside `[0, vehicle_capacity]`
  - using negative pick/drop values, or non-numeric types
- **Stop action rule violation**: at a single stop, specifying both `bikes_picked_up > 0` and `bikes_dropped_off > 0`.
- **Station inventory infeasibility**: final inventory `initial - picked_up + dropped_off` outside `[0, station_capacity]`.
- **Station/vehicle aggregation inconsistencies**:
  - station-level totals don’t equal the sum across all vehicle stops
  - station-level `net_bike_change` not equal to `total_picked_up - total_dropped_off`
- **Unmet amount miscomputed**: not using `abs(net_rebalancing_target - net_bike_change)`, or forgetting to sum across stations, or misapplying `penalty_weight`.
- **Output schema issues**:
  - missing station objects for some stations, or missing vehicle objects for some vehicles
  - missing required keys in `summary`, `vehicles[*]`, `stops[*]`, or `stations[*]`
  - using station names/indices instead of `station_id` values from `data.json`

## Possible procedures
1. **Parse and normalize inputs**
   - Read `data.json`; build station records keyed by `station_id`.
   - Separate stations into:
     - **Supply** candidates: `net_rebalancing_target > 0` (can pick up)
     - **Demand** candidates: `net_rebalancing_target < 0` (need drop off)
   - Track per-station feasible bounds:
     - max pickable given inventory: `initial_bikes` (cannot go below 0)
     - max droppable given free capacity: `station_capacity - initial_bikes` (cannot exceed capacity)

2. **Define the distance function (exactly as required)**
   - Implement great-circle (haversine) with Earth radius **3960.0** miles.
   - Use it consistently for every leg: depot→station, station→station, station→depot.
   - Decide a rounding/precision approach and apply it consistently when summing (keep full precision internally; round only for presentation if needed).

3. **Construct an initial feasible rebalancing plan (quantities first, routes second)**
   - Aim to satisfy as much target as possible while respecting station inventory bounds.
   - Create a feasible “flow” of bikes:
     - total supply available = sum of feasible pick-ups
     - total demand absorbable = sum of feasible drop-offs
   - If total supply ≠ total demand, accept that unmet penalty will occur; still ensure actions remain feasible.

4. **Assign actions to vehicles under capacity constraints**
   - Ensure each vehicle has:
     - a non-empty set of stations (at least one stop)
     - load never negative and never exceeding capacity
   - Common constructive patterns:
     - **Pickup-first then drop-off** tours: start with `start_load = 0`, visit supply stations to load up, then demand stations to unload.
     - **Interleaved** pickup/drop if needed to keep within capacity and non-negativity.
   - Decision points:
     - If a vehicle is at capacity, prefer routing to demand stations next.
     - If a vehicle is near empty and still must serve demand, you must route to a supply station first (or accept unmet demand).

5. **Build routes while respecting “visit at most once per vehicle”**
   - For each vehicle, order its assigned stations using a simple heuristic:
     - nearest-neighbor insertion, or
     - depot → nearest station → … → nearest next station → depot
   - Ensure no station repeats within the same vehicle’s `route`.
   - Keep in mind that multiple vehicles may visit the same station (allowed) unless the task context forbids it (here, only per-vehicle repetition is forbidden).

6. **Compute all derived quantities deterministically**
   - For each vehicle:
     - set `start_load`
     - simulate stops to compute each `load_after_stop`
     - set `end_load` to the last load after final stop
     - compute route distance by summing consecutive legs including depot endpoints
   - For each station:
     - sum `total_bikes_picked_up` and `total_bikes_dropped_off` across all vehicles’ stops at that `station_id`
     - compute `net_bike_change`
     - compute `unmet_rebalancing_amount`
     - (implicitly) ensure final station inventory stays within bounds

7. **Assemble `report.json` in the required schema**
   - Include **all vehicles** (exactly `vehicle_count` objects).
   - Include **all stations** from `data.json` (one object per station).
   - Fill `summary` using:
     - `travel_distance_miles` = total distance across vehicles
     - `total_unmet_rebalancing_amount` = sum across stations
     - `unmet_rebalancing_penalty` = `penalty_weight * total_unmet_rebalancing_amount`
     - `objective` = `travel_distance_miles + unmet_rebalancing_penalty`

8. **Recovery / adjustment loop**
   - If any constraint fails:
     - Fix load infeasibility by reordering stops or splitting quantities across more stops/vehicles.
     - Fix station infeasibility by capping pick/drop at station bounds and pushing remaining requirement into unmet amount (rather than violating capacity).
     - Fix “vehicle must visit stations” by ensuring each vehicle gets at least one station stop (even a small feasible action or a partial fulfillment).

## Verification Checklist
- **Schema completeness**
  - `report.json` has `summary`, `vehicles` (length = `vehicle_count`), and `stations` (length = number of stations in `data.json`).
  - Every vehicle has: `vehicle_id`, `start_load`, `route`, `stops`, `end_load`.
  - Every stop has: `station_id`, `bikes_picked_up`, `bikes_dropped_off`, `load_after_stop`.
  - Every station object has: `station_id`, `net_rebalancing_target`, `total_bikes_picked_up`, `total_bikes_dropped_off`, `net_bike_change`, `unmet_rebalancing_amount`.

- **Route constraints**
  - Each vehicle route begins with `"depot_start"` and ends with `"depot_end"`.
  - Each vehicle visits at least one non-depot station (cannot stay at depot).
  - No vehicle repeats a station within its own route.
  - Every stop `station_id` exists in `data.json`.

- **Action constraints**
  - For every stop: not both pick up and drop off (> 0) at the same stop.
  - All pick/drop amounts are ≥ 0.
  - Load recursion holds exactly: `load_after_stop = previous_load + picked_up - dropped_off`.

- **Capacity / inventory feasibility**
  - For each vehicle: `start_load`, every `load_after_stop`, and `end_load` are within `[0, vehicle_capacity]`.
  - For each station: final inventory `initial - total_picked_up + total_dropped_off` is within `[0, station_capacity]`.

- **Aggregation correctness**
  - Station totals equal the sum of all corresponding stop quantities across all vehicles.
  - `net_bike_change = total_bikes_picked_up - total_bikes_dropped_off`.
  - `unmet_rebalancing_amount = abs(net_rebalancing_target - net_bike_change)`.

- **Objective correctness**
  - Distances computed via great-circle / haversine with Earth radius **3960.0 miles**.
  - `travel_distance_miles` equals the sum across all vehicle route legs (including depot legs).
  - `total_unmet_rebalancing_amount` sums station unmet values.
  - `unmet_rebalancing_penalty = penalty_weight * total_unmet_rebalancing_amount`.
  - `objective = travel_distance_miles + unmet_rebalancing_penalty`.

- **Evaluator-visible constraints / hygiene**
  - Do not copy any concrete IDs/values/paths from unrelated retrieved examples.
  - Preserve unrelated repository state; only add/overwrite the required `report.json`.
  - If any evidence in `data.json` is ambiguous (missing fields, inconsistent units), halt and re-check parsing assumptions rather than guessing silently.
