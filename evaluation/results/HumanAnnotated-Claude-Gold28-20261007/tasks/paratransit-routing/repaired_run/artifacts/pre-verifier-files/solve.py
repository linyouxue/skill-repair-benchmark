#!/usr/bin/env python3
"""Paratransit full-day dial-a-ride solver using OR-Tools."""
import csv
import json
import sys
import time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2


INVALID = 10**6
SERVICE_T = 5
CAP = 3
TW = 30
OP_LO = 300
OP_HI = 1320
SHIFT = 480
SHIFT_STARTS = list(range(300, 840 + 1, 60))
NUM_VEH = 32


def load_data():
    with open("/root/requests.json") as f:
        reqs = json.load(f)
    with open("/root/t_matrix.csv") as f:
        M = [[int(x) for x in r] for r in csv.reader(f)]
    trips = []            # list of dicts (passenger_idx, trip_json)
    passenger_of_trip = []
    pass_sets = []        # list of lists of trip indices
    for pi, p in enumerate(reqs):
        s = []
        for t in p["trips"]:
            s.append(len(trips))
            trips.append(t)
            passenger_of_trip.append(pi)
        pass_sets.append(s)
    return reqs, M, trips, passenger_of_trip, pass_sets


def compute_windows(trips, M, n):
    """Return (pu_window, do_window, infeasible_trip_ids)."""
    pu_win = {}
    do_win = {}
    infeasible = set()
    for i, t in enumerate(trips):
        pu = 1 + i
        do = 1 + n + i
        direct = M[pu][do]
        ea = t["expected_arrival_time"]
        if direct < 0:
            infeasible.add(i); continue
        do_lo = ea - TW
        do_hi = ea
        pu_lo = ea - TW - direct
        pu_hi = ea - direct
        if do_hi > OP_HI or do_lo < OP_LO or pu_hi < OP_LO or M[0][pu] < 0 or M[do][2 * n + 1] < 0:
            infeasible.add(i); continue
        pu_lo = max(pu_lo, OP_LO)
        pu_hi = min(pu_hi, OP_HI)
        do_lo = max(do_lo, OP_LO)
        do_hi = min(do_hi, OP_HI)
        if pu_lo > pu_hi or do_lo > do_hi:
            infeasible.add(i); continue
        pu_win[i] = (pu_lo, pu_hi)
        do_win[i] = (do_lo, do_hi)
    return pu_win, do_win, infeasible


def build_solver_matrix(M, trips, n):
    """Build internal solver node layout and transit matrix.

    Solver nodes:
      [0, 2n)              -> jobs: 0..n-1 pickups, n..2n-1 dropoffs
      [2n, 2n+NUM_VEH)     -> start depot copies
      [2n+NUM_VEH, 2n+2V)  -> end depot copies

    External node id for solver node k:
      pickup i (0-indexed) -> external 1+i
      dropoff i            -> external 1+n+i
      start copy           -> external 0
      end copy             -> external 2n+1
    """
    V = NUM_VEH
    total = 2 * n + 2 * V

    def ext(k):
        if k < n: return 1 + k
        if k < 2 * n: return 1 + n + (k - n)
        if k < 2 * n + V: return 0
        return 2 * n + 1

    def is_depot_copy(k):
        return k >= 2 * n

    def service_at(k):
        # Service time is at the from-node of a transit
        if is_depot_copy(k):
            return 0
        return SERVICE_T  # 5 for both pickup and dropoff for all trips

    # Transit matrix: travel + from-service
    transit = [[0] * total for _ in range(total)]
    for i in range(total):
        ei = ext(i)
        si = service_at(i)
        for j in range(total):
            if i == j:
                transit[i][j] = 0
                continue
            ej = ext(j)
            # start copy -> end copy of SAME vehicle -> 0 handled below
            tt = M[ei][ej]
            if tt < 0:
                transit[i][j] = INVALID
            else:
                transit[i][j] = tt + si
    # Ensure start copy -> own end copy is 0 (empty route allowed)
    for v in range(V):
        s = 2 * n + v
        e = 2 * n + V + v
        transit[s][e] = 0
    # Avoid depot_copy -> other depot copies being used oddly (OR-Tools won't but keep valid)
    return transit, ext


def solve():
    t0 = time.time()
    reqs, M, trips, passenger_of_trip, pass_sets = load_data()
    n = len(trips)
    assert n == 515

    pu_win, do_win, infeasible = compute_windows(trips, M, n)
    print(f"[info] trips={n}, infeasible_trips={len(infeasible)}", flush=True)
    # Determine infeasible passenger sets (any infeasible trip => entire set unservable)
    bad_pass = {passenger_of_trip[i] for i in infeasible}
    forced_skip_trips = set()
    for pi in bad_pass:
        for ti in pass_sets[pi]:
            forced_skip_trips.add(ti)
    print(f"[info] forced_skip_trips={len(forced_skip_trips)} across {len(bad_pass)} passenger sets", flush=True)

    V = NUM_VEH
    transit, ext = build_solver_matrix(M, trips, n)
    total = len(transit)
    start_nodes = [2 * n + v for v in range(V)]
    end_nodes = [2 * n + V + v for v in range(V)]

    manager = pywrapcp.RoutingIndexManager(total, V, start_nodes, end_nodes)
    routing = pywrapcp.RoutingModel(manager)

    # Register transit (used as both time and arc cost)
    transit_cb = routing.RegisterTransitMatrix(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    # Time dimension: slack = allowed wait at a node up to 480 min; horizon = 1320
    routing.AddDimension(transit_cb, 480, OP_HI, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    # Capacity dimension: +1 at pickup, -1 at dropoff, 0 at depots
    def demand(k):
        if k < n: return 1
        if k < 2 * n: return -1
        return 0
    demand_cb = routing.RegisterUnaryTransitVector([demand(k) for k in range(total)])
    routing.AddDimensionWithVehicleCapacity(demand_cb, 0, [CAP] * V, True, "Capacity")

    solver = routing.solver()

    # Pickup-delivery pairs, same vehicle, precedence
    for i in range(n):
        pu_s = i
        do_s = n + i
        pu_idx = manager.NodeToIndex(pu_s)
        do_idx = manager.NodeToIndex(do_s)
        routing.AddPickupAndDelivery(pu_idx, do_idx)
        solver.Add(routing.VehicleVar(pu_idx) == routing.VehicleVar(do_idx))
        solver.Add(time_dim.CumulVar(pu_idx) <= time_dim.CumulVar(do_idx))

    # Time windows and forced-skip handling
    for i in range(n):
        pu_s = i
        do_s = n + i
        pu_idx = manager.NodeToIndex(pu_s)
        do_idx = manager.NodeToIndex(do_s)
        if i in forced_skip_trips:
            # Force skip: deactivate pickup and dropoff.
            routing.ActiveVar(pu_idx).SetValue(0)
            routing.ActiveVar(do_idx).SetValue(0)
            continue
        plo, phi = pu_win[i]
        dlo, dhi = do_win[i]
        time_dim.CumulVar(pu_idx).SetRange(plo, phi)
        time_dim.CumulVar(do_idx).SetRange(dlo, dhi)

    # Grouped disjunction per passenger set (CP-style). Dropoffs are optional with 0 penalty.
    REQ_PENALTY = 100_000
    for pi, s in enumerate(pass_sets):
        if pi in bad_pass:
            continue
        pu_indices = [manager.NodeToIndex(ti) for ti in s]
        routing.AddDisjunction(pu_indices, len(s) * REQ_PENALTY, len(s))
    # Allow each dropoff to be optional at zero penalty
    for i in range(n):
        if i in forced_skip_trips:
            continue
        do_idx = manager.NodeToIndex(n + i)
        routing.AddDisjunction([do_idx], 0)

    # Vehicle shift constraints: start cumul must be in SHIFT_STARTS, span <= 480, end <= OP_HI
    for v in range(V):
        start_idx = routing.Start(v)
        end_idx = routing.End(v)
        time_dim.CumulVar(start_idx).SetRange(OP_LO, SHIFT_STARTS[-1])
        time_dim.CumulVar(start_idx).SetValues(SHIFT_STARTS)
        time_dim.CumulVar(end_idx).SetRange(OP_LO, OP_HI)
        time_dim.SetSpanUpperBoundForVehicle(SHIFT, v)
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(start_idx))
        routing.AddVariableMaximizedByFinalizer(time_dim.CumulVar(end_idx))

    # Search parameters
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    params.log_search = True

    print(f"[info] solving with time limit {params.time_limit.seconds}s...", flush=True)
    solution = routing.SolveWithParameters(params)
    print(f"[info] solve done in {time.time()-t0:.1f}s. status={routing.status()}", flush=True)
    if solution is None:
        print("[error] No solution found")
        return None

    # Extract routes
    V = NUM_VEH
    raw_routes = []
    for v in range(V):
        idx = routing.Start(v)
        stops = []
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            stops.append(node)
            idx = solution.Value(routing.NextVar(idx))
        end_node = manager.IndexToNode(idx)
        stops.append(end_node)
        raw_routes.append(stops)
    return (raw_routes, trips, pass_sets, passenger_of_trip, M, n, forced_skip_trips, solution, routing, manager, time_dim)


def postprocess_and_write(result):
    (raw_routes, trips, pass_sets, passenger_of_trip, M, n, forced_skip_trips,
     solution, routing, manager, time_dim) = result
    V = NUM_VEH

    # Map solver node -> job type/trip index
    def classify(k):
        if k < n: return ("pickup", k)
        if k < 2 * n: return ("dropoff", k - n)
        return ("depot", None)

    def ext_node(k):
        if k < n: return 1 + k
        if k < 2 * n: return 1 + n + (k - n)
        if k < 2 * n + V: return 0
        return 2 * n + 1

    # Which trips did each route visit (both pickup & dropoff on same vehicle)?
    served_trips_per_route = []
    for stops in raw_routes:
        pus = set(); dos = set()
        for s in stops:
            kind, tid = classify(s)
            if kind == "pickup": pus.add(tid)
            elif kind == "dropoff": dos.add(tid)
        served_trips_per_route.append(pus & dos)
    all_served_trips = set().union(*served_trips_per_route) if served_trips_per_route else set()

    # Determine which passenger sets are fully served
    fully_served = set()
    for pi, s in enumerate(pass_sets):
        if all(ti in all_served_trips for ti in s):
            fully_served.add(pi)

    kept_trips = {ti for pi in fully_served for ti in pass_sets[pi]}
    print(f"[info] solver-served trips={len(all_served_trips)}, kept after group filter={len(kept_trips)}", flush=True)

    def audit_route(stops, start_time):
        """Return (feasible, served_trip_ids, cleaned_sequence_of_external, actual_start_time)."""
        # Filter stops: keep depot ends + stops whose trip is in kept_trips.
        filtered_solver = []
        for i, s in enumerate(stops):
            kind, tid = classify(s)
            if kind == "depot":
                filtered_solver.append(s)
            elif tid in kept_trips:
                filtered_solver.append(s)
        # Must still start and end at a depot copy
        if len(filtered_solver) < 2:
            return False, set(), None, None
        # Simulate
        # Find allowed start time: use SHIFT_STARTS, use the latest allowed start that keeps route feasible
        # We'll pick the greatest start_time in SHIFT_STARTS such that first pickup window still works.
        # Simpler: use start_time already from solver; keep it.
        # Convert to external nodes
        ext_seq = [ext_node(s) for s in filtered_solver]
        # Try different shift starts; actually the solver already set a valid start.
        # Here we take solver-provided start_time and simulate.
        cur_time = start_time
        load = 0
        served = set()
        pending_dropoffs = {}
        # Walk through
        for i in range(len(filtered_solver) - 1):
            cur = filtered_solver[i]
            nxt = filtered_solver[i + 1]
            kind, tid = classify(cur)
            ext_cur = ext_node(cur)
            ext_nxt = ext_node(nxt)
            # Service at cur (if not depot)
            if kind == "pickup":
                pu_lo, pu_hi = (trips[tid]["expected_arrival_time"] - TW - M[ext_node(tid):][0] if False else (None, None))
            # Compute arrival (= cur_time if first), service start = max(cur_time, window_lo), departure = start + service
            if i == 0:
                # at depot start — no service
                arrival = cur_time
                departure = arrival
            else:
                arrival = cur_time
                if kind == "pickup":
                    ea = trips[tid]["expected_arrival_time"]
                    direct = M[1 + tid][1 + n + tid]
                    lo = max(ea - TW - direct, OP_LO)
                    hi = min(ea - direct, OP_HI)
                    if arrival > hi: return False, set(), None, None
                    service_start = max(arrival, lo)
                    departure = service_start + SERVICE_T
                    load += 1
                    if load > CAP: return False, set(), None, None
                    pending_dropoffs[tid] = True
                elif kind == "dropoff":
                    ea = trips[tid]["expected_arrival_time"]
                    lo = max(ea - TW, OP_LO)
                    hi = min(ea, OP_HI)
                    if arrival > hi: return False, set(), None, None
                    service_start = max(arrival, lo)
                    departure = service_start + SERVICE_T
                    load -= 1
                    if load < 0: return False, set(), None, None
                    if tid in pending_dropoffs:
                        served.add(tid)
                        del pending_dropoffs[tid]
                else:
                    departure = arrival
            # Travel to next
            travel = M[ext_cur][ext_nxt]
            if travel < 0:
                return False, set(), None, None
            cur_time = departure + travel
        # Final: arrive at end depot
        if cur_time > OP_HI: return False, set(), None, None
        if cur_time - start_time > SHIFT: return False, set(), None, None
        if load != 0: return False, set(), None, None
        if pending_dropoffs: return False, set(), None, None
        return True, served, ext_seq, start_time

    # Rebuild routes
    routes_out = []
    total_served = 0
    for v, stops in enumerate(raw_routes):
        start_idx = routing.Start(v)
        start_time = solution.Value(time_dim.CumulVar(start_idx))
        feas, served, ext_seq, actual_start = audit_route(stops, start_time)
        if not feas:
            # If infeasible after filter, try without filter (shouldn't happen); skip route
            print(f"[warn] route {v} infeasible after filter; skipping its service", flush=True)
            continue
        # Only emit if route has service stops (not just depot->depot)
        service_count = len(ext_seq) - 2
        if service_count == 0:
            continue
        routes_out.append({
            "vehicle_id": f"V{v}",
            "start_time": int(actual_start),
            "node_sequence": [int(x) for x in ext_seq],
        })
        total_served += len(served)
    print(f"[info] final served trips={total_served} in {len(routes_out)} routes", flush=True)

    with open("/root/report.json", "w") as f:
        json.dump({"routes": routes_out}, f)
    print("[info] wrote /root/report.json", flush=True)


if __name__ == "__main__":
    res = solve()
    if res is not None:
        postprocess_and_write(res)
    else:
        print("[error] no solution; writing empty")
        with open("/root/report.json", "w") as f:
            json.dump({"routes": []}, f)
