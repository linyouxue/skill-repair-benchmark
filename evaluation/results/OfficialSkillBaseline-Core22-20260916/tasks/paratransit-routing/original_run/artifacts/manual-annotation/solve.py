import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from ortools.constraint_solver import pywrapcp, routing_enums_pb2


ROOT = Path("/root")


@dataclass(frozen=True)
class Trip:
    trip_index: int  # 0..n-1 in flattened order
    passenger_id: str
    passenger_count: int
    expected_arrival_time: int
    pickup_service_time: int
    dropoff_service_time: int

    @property
    def pickup_node(self) -> int:
        return 1 + self.trip_index

    def dropoff_node(self, n: int) -> int:
        return 1 + n + self.trip_index


def read_instance_config(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def read_requests(path: Path) -> Tuple[List[Trip], Dict[str, List[int]]]:
    with path.open() as f:
        passengers = json.load(f)

    trips: List[Trip] = []
    passenger_to_trip_indices: Dict[str, List[int]] = {}

    for p in passengers:
        pid = p["passenger_id"]
        passenger_to_trip_indices.setdefault(pid, [])
        for t in p["trips"]:
            trip_index = len(trips)
            trips.append(
                Trip(
                    trip_index=trip_index,
                    passenger_id=pid,
                    passenger_count=int(t["passenger_count"]),
                    expected_arrival_time=int(t["expected_arrival_time"]),
                    pickup_service_time=int(t["pickup_service_time"]),
                    dropoff_service_time=int(t["dropoff_service_time"]),
                )
            )
            passenger_to_trip_indices[pid].append(trip_index)

    return trips, passenger_to_trip_indices


def read_matrix_csv(path: Path) -> List[List[int]]:
    matrix: List[List[int]] = []
    with path.open(newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            matrix.append([int(x) for x in row])

    if not matrix:
        raise ValueError("Empty travel time matrix")

    n = len(matrix)
    if any(len(r) != n for r in matrix):
        raise ValueError("Travel matrix is not square")

    return matrix


def build_and_solve(
    trips: List[Trip],
    passenger_to_trip_indices: Dict[str, List[int]],
    travel_time: List[List[int]],
    nb_vehicles: int,
    vehicle_capacity: int,
    time_window_width: int,
    time_limit_seconds: int = 120,
) -> Tuple[dict, dict]:
    n = len(trips)
    start_depot = 0
    end_depot = 2 * n + 1
    num_nodes = 2 * n + 2

    if len(travel_time) != num_nodes:
        raise ValueError(
            f"Matrix size {len(travel_time)} does not match expected {num_nodes}"
        )

    invalid_time = 1_000_000

    # Service time per node.
    service_time = [0] * num_nodes
    demand = [0] * num_nodes
    dropoff_expected = [None] * num_nodes  # type: ignore[list-item]
    passenger_count_by_trip = [0] * n

    for tr in trips:
        p = tr.pickup_node
        d = tr.dropoff_node(n)
        service_time[p] = tr.pickup_service_time
        service_time[d] = tr.dropoff_service_time
        demand[p] = tr.passenger_count
        demand[d] = -tr.passenger_count
        dropoff_expected[d] = tr.expected_arrival_time
        passenger_count_by_trip[tr.trip_index] = tr.passenger_count

    # Precompute time and cost matrices (travel + service for time dimension).
    time_matrix = [[0] * num_nodes for _ in range(num_nodes)]
    cost_matrix = [[0] * num_nodes for _ in range(num_nodes)]
    invalid_arcs = 0
    for i in range(num_nodes):
        si = service_time[i]
        row_t = time_matrix[i]
        row_c = cost_matrix[i]
        ext_row = travel_time[i]
        for j in range(num_nodes):
            tt = ext_row[j]
            if tt < 0:
                invalid_arcs += 1
                row_t[j] = invalid_time
                row_c[j] = invalid_time
            else:
                row_t[j] = tt + si
                row_c[j] = tt

    starts = [start_depot] * nb_vehicles
    ends = [end_depot] * nb_vehicles
    manager = pywrapcp.RoutingIndexManager(num_nodes, nb_vehicles, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    time_cb = routing.RegisterTransitMatrix(time_matrix)
    cost_cb = routing.RegisterTransitMatrix(cost_matrix)
    routing.SetArcCostEvaluatorOfAllVehicles(cost_cb)

    # Time dimension: allow waiting. Use a horizon large enough to hold
    # all stated time windows, while enforcing end-of-day through depot bounds.
    max_expected = max(tr.expected_arrival_time for tr in trips) if trips else 1320
    horizon = max(1320, max_expected)
    routing.AddDimension(
        time_cb,
        horizon,  # slack (waiting)
        horizon,
        False,
        "Time",
    )
    time_dim = routing.GetDimensionOrDie("Time")

    # Capacity dimension.
    demand_cb = routing.RegisterUnaryTransitVector(demand)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb,
        0,
        [vehicle_capacity] * nb_vehicles,
        True,
        "Capacity",
    )

    solver = routing.solver()

    # Shift start times: hourly from 300..840.
    allowed_starts = list(range(300, 841, 60))
    for v in range(nb_vehicles):
        start_idx = routing.Start(v)
        end_idx = routing.End(v)
        time_dim.CumulVar(start_idx).SetRange(300, 840)
        time_dim.CumulVar(start_idx).SetValues(allowed_starts)
        time_dim.CumulVar(end_idx).SetRange(0, 1320)
        time_dim.SetSpanUpperBoundForVehicle(480, v)

        # Help finalizer pick a concrete start/end time.
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(start_idx))
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(end_idx))

    # Time windows for pickups/dropoffs derived from expected arrival time.
    for tr in trips:
        p_node = tr.pickup_node
        d_node = tr.dropoff_node(n)

        direct = travel_time[p_node][d_node]
        if direct < 0:
            # Trip is inherently unusable; leave windows tight so it will be skipped.
            direct = invalid_time

        drop_low = max(0, tr.expected_arrival_time - time_window_width)
        drop_high = tr.expected_arrival_time
        pick_low = max(0, tr.expected_arrival_time - time_window_width - direct)
        pick_high = max(0, tr.expected_arrival_time - direct)

        p_idx = manager.NodeToIndex(p_node)
        d_idx = manager.NodeToIndex(d_node)
        time_dim.CumulVar(p_idx).SetRange(pick_low, pick_high)
        time_dim.CumulVar(d_idx).SetRange(drop_low, drop_high)

    # Optional visits and pickup-and-delivery constraints.
    # Penalty tuned to dominate all routing costs so served-count is primary.
    skip_penalty_per_trip = 1_000_000

    pickup_indices: List[int] = [0] * n
    dropoff_indices: List[int] = [0] * n

    for tr in trips:
        p_idx = manager.NodeToIndex(tr.pickup_node)
        d_idx = manager.NodeToIndex(tr.dropoff_node(n))
        pickup_indices[tr.trip_index] = p_idx
        dropoff_indices[tr.trip_index] = d_idx

        # Make both pickup and dropoff optional; tie activity so the pair is served together.
        routing.AddDisjunction([p_idx], skip_penalty_per_trip)
        routing.AddDisjunction([d_idx], skip_penalty_per_trip)

        routing.AddPickupAndDelivery(p_idx, d_idx)
        solver.Add(routing.VehicleVar(p_idx) == routing.VehicleVar(d_idx))
        solver.Add(time_dim.CumulVar(p_idx) <= time_dim.CumulVar(d_idx))
        solver.Add(routing.ActiveVar(p_idx) == routing.ActiveVar(d_idx))

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GENERIC_TABU_SEARCH
    )
    params.time_limit.seconds = int(time_limit_seconds)
    params.log_search = True

    solution = routing.SolveWithParameters(params)
    if solution is None:
        raise RuntimeError("No solution found")

    # Extract routes.
    routes = []
    for v in range(nb_vehicles):
        index = routing.Start(v)
        next_index = solution.Value(routing.NextVar(index))
        if routing.IsEnd(next_index):
            continue

        start_time = solution.Value(time_dim.CumulVar(routing.Start(v)))

        node_sequence = [start_depot]
        while not routing.IsEnd(index):
            index = solution.Value(routing.NextVar(index))
            node_sequence.append(manager.IndexToNode(index))

        routes.append(
            {
                "vehicle_id": f"V{v}",
                "start_time": int(start_time),
                "node_sequence": [int(x) for x in node_sequence],
            }
        )

    report = {"routes": routes}

    # Collect some lightweight stats for logging.
    served_pickups = 0
    for tr in trips:
        if solution.Value(routing.ActiveVar(pickup_indices[tr.trip_index])) == 1:
            served_pickups += 1

    stats = {
        "trips": n,
        "vehicles": nb_vehicles,
        "invalid_arcs": invalid_arcs,
        "served_trips": served_pickups,
        "routes_used": len(routes),
        "objective": int(solution.ObjectiveValue()),
    }

    return report, stats


def audit_report(
    report: dict,
    trips: List[Trip],
    passenger_to_trip_indices: Dict[str, List[int]],
    travel_time: List[List[int]],
    vehicle_capacity: int,
    time_window_width: int,
) -> dict:
    n = len(trips)
    end_depot = 2 * n + 1

    pickup_by_node = {tr.pickup_node: tr for tr in trips}
    dropoff_by_node = {tr.dropoff_node(n): tr for tr in trips}

    # Track per trip served and per passenger completeness.
    trip_served = [False] * n

    violations: List[str] = []

    for r in report.get("routes", []):
        start_time = int(r["start_time"])
        seq = r["node_sequence"]
        if not seq or seq[0] != 0 or seq[-1] != end_depot:
            violations.append(f"Route {r.get('vehicle_id')} depot endpoints invalid")
            continue

        if start_time % 60 != 0 or not (300 <= start_time <= 840):
            violations.append(f"Route {r.get('vehicle_id')} start_time not allowed")

        t = start_time
        load = 0
        seen_pickups = set()

        for a, b in zip(seq, seq[1:]):
            tt = travel_time[a][b]
            if tt < 0:
                violations.append(
                    f"Route {r.get('vehicle_id')} uses invalid arc {a}->{b}"
                )
                tt = 0
            t += tt

            service = 0
            win_low = None
            win_high = None

            if b in pickup_by_node:
                tr = pickup_by_node[b]
                direct = travel_time[tr.pickup_node][tr.dropoff_node(n)]
                if direct < 0:
                    direct = 10**9
                win_low = max(0, tr.expected_arrival_time - time_window_width - direct)
                win_high = max(0, tr.expected_arrival_time - direct)
                service = tr.pickup_service_time

            elif b in dropoff_by_node:
                tr = dropoff_by_node[b]
                win_low = max(0, tr.expected_arrival_time - time_window_width)
                win_high = tr.expected_arrival_time
                service = tr.dropoff_service_time

            # Wait until window opens; arrival_time is service start time.
            if win_low is not None and win_high is not None:
                if t < win_low:
                    t = win_low
                if t > win_high:
                    violations.append(
                        f"Node {b} time window violated at {t} > {win_high}"
                    )

            if b in pickup_by_node:
                tr = pickup_by_node[b]
                load += tr.passenger_count
                if load > vehicle_capacity or load < 0:
                    violations.append(
                        f"Capacity violated after pickup node {b}: load {load}"
                    )
                seen_pickups.add(tr.trip_index)

            elif b in dropoff_by_node:
                tr = dropoff_by_node[b]
                if tr.trip_index not in seen_pickups:
                    violations.append(
                        f"Dropoff before pickup for trip {tr.trip_index}"
                    )
                load -= tr.passenger_count
                if load > vehicle_capacity or load < 0:
                    violations.append(
                        f"Capacity violated after dropoff node {b}: load {load}"
                    )

            t += service

        if t > 1320:
            violations.append(f"Route {r.get('vehicle_id')} ends after 1320: {t}")
        if t - start_time > 480:
            violations.append(
                f"Route {r.get('vehicle_id')} exceeds shift length: {t-start_time}"
            )
        if load != 0:
            violations.append(f"Route {r.get('vehicle_id')} ends with load {load}")

        # Mark trips served if pickup and dropoff both in sequence.
        nodes = set(seq)
        for tr in trips:
            if tr.pickup_node in nodes and tr.dropoff_node(n) in nodes:
                trip_served[tr.trip_index] = True

    # Apply passenger all-or-none rule for counting.
    passenger_served_trips = 0
    unserved_due_to_incomplete = 0
    for pid, tlist in passenger_to_trip_indices.items():
        if all(trip_served[i] for i in tlist):
            passenger_served_trips += len(tlist)
        else:
            unserved_due_to_incomplete += sum(1 for i in tlist if trip_served[i])

    return {
        "violations": violations,
        "served_trips_after_passenger_rule": passenger_served_trips,
        "trips_served_but_discarded_by_passenger_rule": unserved_due_to_incomplete,
    }


def main() -> None:
    cfg = read_instance_config(ROOT / "instance_config.json")
    trips, passenger_to_trip_indices = read_requests(ROOT / "requests.json")
    travel_time = read_matrix_csv(ROOT / "t_matrix.csv")

    report, stats = build_and_solve(
        trips=trips,
        passenger_to_trip_indices=passenger_to_trip_indices,
        travel_time=travel_time,
        nb_vehicles=int(cfg["nb_vehicles"]),
        vehicle_capacity=int(cfg["vehicle_capacity"]),
        time_window_width=int(cfg["time_window_width"]),
        time_limit_seconds=120,
    )

    audit = audit_report(
        report=report,
        trips=trips,
        passenger_to_trip_indices=passenger_to_trip_indices,
        travel_time=travel_time,
        vehicle_capacity=int(cfg["vehicle_capacity"]),
        time_window_width=int(cfg["time_window_width"]),
    )

    # Fail fast if our own audit finds violations.
    if audit["violations"]:
        raise SystemExit(
            "Audit violations found:\n" + "\n".join(audit["violations"][:50])
        )

    out_path = ROOT / "report.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")

    print(json.dumps({"stats": stats, "audit": audit}, indent=2))


if __name__ == "__main__":
    main()
