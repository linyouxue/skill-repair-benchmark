#!/usr/bin/env python3
"""Paratransit full-day planner using OR-Tools RoutingModel.

Nodes:
  0            : start depot
  1..n         : pickups
  n+1..2n      : dropoffs
  2n+1         : end depot
"""
import csv
import json
import time
from collections import defaultdict
from ortools.constraint_solver import pywrapcp, routing_enums_pb2


# ---------- load data ----------

CONFIG = json.load(open("/root/instance_config.json"))
REQUESTS = json.load(open("/root/requests.json"))

NB_PASSENGERS = CONFIG["nb_passengers"]
NB_TRIPS = CONFIG["nb_trips"]
NB_VEHICLES = CONFIG["nb_vehicles"]
VEHICLE_CAPACITY = CONFIG["vehicle_capacity"]
TIME_WINDOW_WIDTH = CONFIG["time_window_width"]

START_DEPOT = 0
END_DEPOT = 2 * NB_TRIPS + 1
N_NODES = 2 * NB_TRIPS + 2

OPERATING_LOW, OPERATING_HIGH = 300, 1320
SHIFT_DURATION = 480
SHIFT_STARTS = list(range(300, 841, 60))  # 300..840 inclusive, hourly
SKIP_PENALTY = 1_000_000  # per trip; dominates any travel cost

with open("/root/t_matrix.csv") as f:
    T = [[int(v) for v in row] for row in csv.reader(f)]
assert len(T) == N_NODES

# Flatten trips in file order; build parallel arrays
trip_passenger_set_id = [None] * NB_TRIPS      # 0..NB_PASSENGERS-1
trip_ids = [None] * NB_TRIPS                   # external trip ids
trip_eat = [0] * NB_TRIPS
trip_pickup_svc = [0] * NB_TRIPS
trip_dropoff_svc = [0] * NB_TRIPS
trip_pcount = [0] * NB_TRIPS
passenger_ids = []
passenger_trip_indices = []                    # list of lists of flat trip index

flat = 0
for pset_id, p in enumerate(REQUESTS):
    passenger_ids.append(p["passenger_id"])
    local = []
    for t in p["trips"]:
        trip_passenger_set_id[flat] = pset_id
        trip_ids[flat] = t["trip_id"]
        trip_eat[flat] = t["expected_arrival_time"]
        trip_pickup_svc[flat] = t["pickup_service_time"]
        trip_dropoff_svc[flat] = t["dropoff_service_time"]
        trip_pcount[flat] = t["passenger_count"]
        local.append(flat)
        flat += 1
    passenger_trip_indices.append(local)
assert flat == NB_TRIPS


def pickup_node(i): return 1 + i
def dropoff_node(i): return 1 + NB_TRIPS + i


# ---------- compute time windows ----------

trip_pickup_window = [None] * NB_TRIPS
trip_dropoff_window = [None] * NB_TRIPS
infeasible_trips = set()
for i in range(NB_TRIPS):
    pu, do = pickup_node(i), dropoff_node(i)
    direct = T[pu][do]
    if direct < 0:
        infeasible_trips.add(i)
        continue
    eat = trip_eat[i]
    d_lo, d_hi = eat - TIME_WINDOW_WIDTH, eat
    p_lo, p_hi = eat - TIME_WINDOW_WIDTH - direct, eat - direct
    # Clip to operating range; pickup must occur after shift start >= 300
    d_lo_c, d_hi_c = max(d_lo, OPERATING_LOW), min(d_hi, OPERATING_HIGH)
    p_lo_c, p_hi_c = max(p_lo, OPERATING_LOW), min(p_hi, OPERATING_HIGH)
    # Must also allow dropoff service + return to depot <= 1320
    # dropoff arrival + dropoff_svc + T[do][END_DEPOT] <= 1320
    ret = T[do][END_DEPOT]
    d_hi_c = min(d_hi_c, OPERATING_HIGH - trip_dropoff_svc[i] - ret)
    # Pickup must start no earlier than depot->pickup travel from earliest shift start
    # (shift_start_min=300, start depot service=0). pickup arrival >= 300 + T[0][pu]
    p_lo_c = max(p_lo_c, OPERATING_LOW + T[START_DEPOT][pu])
    # Pickup must leave enough time for pickup_svc + direct + dropoff_svc + return
    p_hi_c = min(p_hi_c, OPERATING_HIGH - trip_pickup_svc[i] - direct - trip_dropoff_svc[i] - ret)
    if p_lo_c > p_hi_c or d_lo_c > d_hi_c:
        infeasible_trips.add(i)
        continue
    trip_pickup_window[i] = (p_lo_c, p_hi_c)
    trip_dropoff_window[i] = (d_lo_c, d_hi_c)

# Any passenger with an infeasible trip is wholly infeasible
infeasible_passengers = set()
for pset_id, trips in enumerate(passenger_trip_indices):
    if any(t in infeasible_trips for t in trips):
        infeasible_passengers.add(pset_id)
        for t in trips:
            infeasible_trips.add(t)

print(f"Infeasible trips: {len(infeasible_trips)}; "
      f"infeasible passengers: {len(infeasible_passengers)}")


# ---------- build routing model ----------

starts = [START_DEPOT] * NB_VEHICLES
ends = [END_DEPOT] * NB_VEHICLES
manager = pywrapcp.RoutingIndexManager(N_NODES, NB_VEHICLES, starts, ends)
routing = pywrapcp.RoutingModel(manager)
solver = routing.solver()

# service time per external node
service = [0] * N_NODES
for i in range(NB_TRIPS):
    service[pickup_node(i)] = trip_pickup_svc[i]
    service[dropoff_node(i)] = trip_dropoff_svc[i]

num_indices = routing.Size() + NB_VEHICLES  # total internal indices incl. end
index_to_node = [manager.IndexToNode(i) for i in range(num_indices)]

# Build full index-indexed matrices.
# Invalid arcs in T are only start-incoming and end-outgoing arcs that routing
# never traverses by construction, so a benign 0 is safe here.
time_matrix = [[0] * num_indices for _ in range(num_indices)]
cost_matrix = [[0] * num_indices for _ in range(num_indices)]
for i in range(num_indices):
    ni = index_to_node[i]
    si = service[ni]
    row_t = time_matrix[i]
    row_c = cost_matrix[i]
    for j in range(num_indices):
        nj = index_to_node[j]
        tt = T[ni][nj]
        if tt < 0:
            row_t[j] = 0
            row_c[j] = 0
        else:
            row_t[j] = tt + si
            row_c[j] = tt

time_cb = routing.RegisterTransitMatrix(time_matrix)
cost_cb = routing.RegisterTransitMatrix(cost_matrix)
routing.SetArcCostEvaluatorOfAllVehicles(cost_cb)

routing.AddDimension(time_cb, 1320, 1320, False, "Time")
time_dim = routing.GetDimensionOrDie("Time")

# capacity: +1 at pickup, -1 at dropoff
demand = [0] * N_NODES
for i in range(NB_TRIPS):
    demand[pickup_node(i)] = trip_pcount[i]
    demand[dropoff_node(i)] = -trip_pcount[i]
demand_vec = [demand[index_to_node[i]] for i in range(num_indices)]
demand_cb = routing.RegisterUnaryTransitVector(demand_vec)
routing.AddDimensionWithVehicleCapacity(
    demand_cb, 0, [VEHICLE_CAPACITY] * NB_VEHICLES, True, "Capacity"
)

# vehicle shift constraints
for v in range(NB_VEHICLES):
    s = routing.Start(v)
    e = routing.End(v)
    time_dim.CumulVar(s).SetRange(SHIFT_STARTS[0], SHIFT_STARTS[-1])
    time_dim.CumulVar(s).SetValues(SHIFT_STARTS)
    time_dim.CumulVar(e).SetRange(OPERATING_LOW, OPERATING_HIGH)
    time_dim.SetSpanUpperBoundForVehicle(SHIFT_DURATION, v)
    routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(s))
    routing.AddVariableMaximizedByFinalizer(time_dim.CumulVar(e))

# pickup-delivery pairs + time windows
for i in range(NB_TRIPS):
    pu_idx = manager.NodeToIndex(pickup_node(i))
    do_idx = manager.NodeToIndex(dropoff_node(i))
    routing.AddPickupAndDelivery(pu_idx, do_idx)
    solver.Add(routing.VehicleVar(pu_idx) == routing.VehicleVar(do_idx))
    solver.Add(time_dim.CumulVar(pu_idx) <= time_dim.CumulVar(do_idx))

    if i in infeasible_trips:
        # keep window generous; disjunction will drop it
        time_dim.CumulVar(pu_idx).SetRange(OPERATING_LOW, OPERATING_HIGH)
        time_dim.CumulVar(do_idx).SetRange(OPERATING_LOW, OPERATING_HIGH)
    else:
        plo, phi = trip_pickup_window[i]
        dlo, dhi = trip_dropoff_window[i]
        time_dim.CumulVar(pu_idx).SetRange(plo, phi)
        time_dim.CumulVar(do_idx).SetRange(dlo, dhi)

# connected-request-set disjunctions (grouped on pickups), dropoffs zero-penalty optional
for pset_id, trips in enumerate(passenger_trip_indices):
    pickup_indices = [manager.NodeToIndex(pickup_node(t)) for t in trips]
    k = len(trips)
    if pset_id in infeasible_passengers:
        # Force skip: individual zero penalty disjunctions on each pickup
        for pi in pickup_indices:
            routing.AddDisjunction([pi], 0)
    else:
        routing.AddDisjunction(pickup_indices, k * SKIP_PENALTY, k)
    for t in trips:
        routing.AddDisjunction([manager.NodeToIndex(dropoff_node(t))], 0)


# ---------- search ----------

params = pywrapcp.DefaultRoutingSearchParameters()
params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GENERIC_TABU_SEARCH
params.time_limit.FromSeconds(60)
params.log_search = True

print("Solving...", flush=True)
t0 = time.time()
solution = routing.SolveWithParameters(params)
print(f"Solve done in {time.time() - t0:.1f}s", flush=True)

if solution is None:
    raise SystemExit("No solution found")


# ---------- extract raw routes ----------

raw_routes = []
for v in range(NB_VEHICLES):
    idx = routing.Start(v)
    seq = []
    while not routing.IsEnd(idx):
        seq.append(index_to_node[idx])
        idx = solution.Value(routing.NextVar(idx))
    seq.append(index_to_node[idx])
    # start-time (what solver chose)
    start_time = solution.Value(time_dim.CumulVar(routing.Start(v)))
    raw_routes.append({"vehicle": v, "start_time": start_time, "seq": seq})


# ---------- audit solver routes and emit output ----------
# Routes are emitted as-is; the connected-set rule is handled at scoring.

def audit_route(seq, start_time):
    """Walk sequence; return (ok, visited_pickup_trip_ids, visited_dropoff_trip_ids)."""
    cur = seq[0]
    t = start_time
    load = 0
    pu_set, do_set = set(), set()
    for nxt in seq[1:]:
        tt = T[cur][nxt]
        if tt < 0:
            return False, None, None
        t = t + service[cur] + tt
        if nxt == END_DEPOT:
            if t > OPERATING_HIGH or t > start_time + SHIFT_DURATION:
                return False, None, None
        else:
            if 1 <= nxt <= NB_TRIPS:
                i = nxt - 1
                if i in infeasible_trips:
                    return False, None, None
                lo, hi = trip_pickup_window[i]
                load += trip_pcount[i]
                pu_set.add(i)
            else:
                i = nxt - 1 - NB_TRIPS
                if i in infeasible_trips:
                    return False, None, None
                lo, hi = trip_dropoff_window[i]
                load -= trip_pcount[i]
                do_set.add(i)
            if t > hi:
                return False, None, None
            if t < lo:
                t = lo
            if load < 0 or load > VEHICLE_CAPACITY:
                return False, None, None
        cur = nxt
    if load != 0:
        return False, None, None
    return True, pu_set, do_set


final_routes = []
served_trips = set()
for r in raw_routes:
    inner = r["seq"][1:-1]
    if not inner:
        continue
    seq = [START_DEPOT] + inner + [END_DEPOT]
    # Try solver's chosen start first; fall back to any legal shift start.
    starts_to_try = [r["start_time"]] + [s for s in SHIFT_STARTS if s != r["start_time"]]
    chosen, visited = None, None
    for st in starts_to_try:
        if st not in SHIFT_STARTS:
            continue
        ok, pu, do = audit_route(seq, st)
        if ok:
            chosen, visited = st, (pu, do)
            break
    if chosen is None:
        # Debug: show solver's route detail
        print(f"WARN vehicle {r['vehicle']} start={r['start_time']} seq_len={len(seq)}")
        # Re-run audit with verbose info for first few failing routes
        if r['vehicle'] < 5:
            print(f"  solver cumul times:")
            idx = routing.Start(r['vehicle'])
            while True:
                node = index_to_node[idx]
                tv = solution.Value(time_dim.CumulVar(idx))
                lo = time_dim.CumulVar(idx).Min()
                hi = time_dim.CumulVar(idx).Max()
                print(f"    idx={idx} node={node} time={tv} window=[{lo},{hi}]")
                if routing.IsEnd(idx):
                    break
                idx = solution.Value(routing.NextVar(idx))
        continue
    pu_set, do_set = visited
    for i in pu_set & do_set:
        served_trips.add(i)
    final_routes.append({
        "vehicle_id": f"V{r['vehicle']}",
        "start_time": chosen,
        "node_sequence": seq,
    })

# apply connected-request-set accounting for reporting
served_by_set = 0
for pset_id, trips in enumerate(passenger_trip_indices):
    if pset_id in infeasible_passengers:
        continue
    if all(t in served_trips for t in trips):
        served_by_set += len(trips)

print(f"Routes used: {len(final_routes)}")
print(f"Trips with both pickup+dropoff visited: {len(served_trips)}")
print(f"Trips served under connected-set rule: {served_by_set} / {NB_TRIPS}")

json.dump({"routes": final_routes}, open("/root/report.json", "w"), indent=2)
print("Wrote /root/report.json")
