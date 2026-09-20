---
name: ortools-routing-modeling
description: Build OR-Tools RoutingModel vehicle-routing models with transit matrices, dimensions, capacity constraints, time windows, optional visits, invalid-arc handling, search parameters, and route extraction.
---

# OR-Tools Routing Modeling

Use this skill for vehicle-routing models built with `ortools.constraint_solver.pywrapcp.RoutingModel`.



## Data And Indexing

- Convert travel times, service times, demands, and time bounds to integers before registering callbacks or transit matrices. Avoid floats and `NaN`; OR-Tools can silently treat bad values as usable arcs.
- Assert that matrix dimensions, node counts, vehicle counts, and declared record counts agree before building the model. Shape mistakes often produce plausible but meaningless routes.
- Keep a clear distinction between external node IDs, routing manager node IDs, and internal routing indices. Convert with `manager.NodeToIndex(node)` and `manager.IndexToNode(index)`.
- When vehicles need distinct starts or ends but the input has shared depots, copy the depot into one internal start node and one internal end node per vehicle. Prefer these internal depot copies over reusing the same shared depot node for every vehicle, then map the copies back to the shared external depot IDs when reporting.
- A common cloned-depot layout is: solver job nodes first, then one start depot per vehicle, then one end depot per vehicle. External shared depot IDs can be stripped from the job matrix and restored only when reporting.
- Treat negative, missing, or sentinel travel times as invalid arcs. Either forbid them with explicit constraints or give them a prohibitive transit cost and reject any final route that uses them. Choose invalid-arc sentinels large enough to dominate feasible legs, but small enough to avoid integer overflow when service times and route spans are added.
- For static integer data, prefer precomputed `RegisterTransitMatrix` and `RegisterUnaryTransitVector` calls over Python callbacks. Routing callbacks are called very often during local search and can consume solve time on large instances.

When an input matrix has one shared start depot and one shared end depot, but the routing model needs one start and end node per vehicle, build an internal matrix with cloned depots:

```python
def clone_depots_matrix(external, job_nodes, num_vehicles, start_depot, end_depot, invalid_cost):
    num_jobs = len(job_nodes)
    start_nodes = list(range(num_jobs, num_jobs + num_vehicles))
    end_nodes = list(range(num_jobs + num_vehicles, num_jobs + 2 * num_vehicles))
    matrix = [[invalid_cost] * (num_jobs + 2 * num_vehicles) for _ in range(num_jobs + 2 * num_vehicles)]

    for i, ext_i in enumerate(job_nodes):
        for j, ext_j in enumerate(job_nodes):
            matrix[i][j] = external[ext_i][ext_j]
        for end in end_nodes:
            matrix[i][end] = external[ext_i][end_depot]

    for start in start_nodes:
        for j, ext_j in enumerate(job_nodes):
            matrix[start][j] = external[start_depot][ext_j]
    for vehicle in range(num_vehicles):
        matrix[start_nodes[vehicle]][end_nodes[vehicle]] = 0
    return matrix, start_nodes, end_nodes
```

## Dimensions

- Put travel time plus service time at the departing node in the time transit. Then `Time.CumulVar(index)` is the arrival or service-start time, and departure is `arrival + service_time`.
- Derive the time horizon from the data, including latest time windows, service time, travel time, and slack. Avoid arbitrary horizons that are too tight for waiting/service or so large that invalid-arc penalties become usable.
- Choose `fix_start_cumul_to_zero` deliberately. Use `False` when vehicle start times or shifts may vary; use start time windows or allowed start values instead.
- Set each vehicle start/end cumul through `routing.Start(vehicle)` and `routing.End(vehicle)`, especially when depots are cloned or shared.
- If shifts may start from a discrete menu, apply allowed values to each vehicle start cumul after setting its broad time-window range.
- Use span upper bounds for route-duration or shift-length limits.
- For capacity, use a unary demand callback and no slack. With OR-Tools dimensions, the load cumul at a node often represents load before applying that node's demand, so audit route loads from the ordered node sequence when checking or exporting a solution.

Apply ordinary visit time windows directly to the node's time cumul:

```python
for node, (window_low, window_high) in time_windows.items():
    index = manager.NodeToIndex(node)
    time_dim.CumulVar(index).SetRange(int(window_low), int(window_high))
```

For top-of-hour shift starts inside an operating window, generate the allowed start values and apply them to each vehicle start cumul:

```python
def possible_shift_start_times(operating_window, shift_duration, step_minutes=60):
    start, end = operating_window
    return [
        minute
        for minute in range(0, 24 * 60 + 1, step_minutes)
        if start <= minute <= end - shift_duration
    ]

shift_starts = possible_shift_start_times(operating_window, shift_duration)
for vehicle in range(num_vehicles):
    time_dim.CumulVar(routing.Start(vehicle)).SetRange(*operating_window)
    time_dim.CumulVar(routing.End(vehicle)).SetRange(*operating_window)
    time_dim.CumulVar(routing.Start(vehicle)).SetValues(shift_starts)
    time_dim.SetSpanUpperBoundForVehicle(shift_duration, vehicle)
    routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.Start(vehicle)))
    routing.AddVariableMaximizedByFinalizer(time_dim.CumulVar(routing.End(vehicle)))
```

## Optional Visits And Objectives

- Use `AddDisjunction` for optional nodes and choose penalties so the primary objective dominates secondary route costs.
- If optional visits are part of the model, scale skip penalties so they reflect the stated priority relative to travel or duration costs.
- When the public objective is to maximize served visits or jobs, model that as large skip penalties, then add a small positive arc cost such as travel time or travel-plus-service time as a secondary tie-breaker. A purely zero-cost served-route objective can give local search too little gradient to improve route structure.
- Keep the skip penalty very large: one additional served job should dominate any plausible secondary travel or service-time difference.
- You can use separate callbacks for optimization cost and time feasibility. The time dimension should enforce travel and service propagation, while the arc-cost callback can use scaled travel or travel-plus-service costs for search guidance.

## Compact Matrix Model Skeleton

Use this shape for large matrix-based routing models with cloned depots, time propagation, capacity, a secondary travel-cost objective, and a bounded local search. Add problem-specific visits, disjunctions, and time windows after creating the dimensions.

```python
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

start_nodes = list(range(job_node_count, job_node_count + num_vehicles))
end_nodes = list(range(job_node_count + num_vehicles, job_node_count + 2 * num_vehicles))
manager = pywrapcp.RoutingIndexManager(num_solver_nodes, num_vehicles, start_nodes, end_nodes)
routing = pywrapcp.RoutingModel(manager)

nodes_from_indices = [manager.IndexToNode(index) for index in range(manager.GetNumberOfIndices())]
time_matrix = [
    [int(travel_times[i][j] + service_times[i]) for j in nodes_from_indices]
    for i in nodes_from_indices
]
cost_matrix = [
    [int(arc_costs[i][j]) for j in nodes_from_indices]
    for i in nodes_from_indices
]
time_cb = routing.RegisterTransitMatrix(time_matrix)
cost_cb = routing.RegisterTransitMatrix(cost_matrix)
routing.SetArcCostEvaluatorOfAllVehicles(cost_cb)
routing.AddDimension(time_cb, waiting_slack, time_horizon, False, "Time")
time_dim = routing.GetDimensionOrDie("Time")

demand_cb = routing.RegisterUnaryTransitVector([int(demands[node]) for node in nodes_from_indices])
routing.AddDimensionWithVehicleCapacity(demand_cb, 0, vehicle_capacities, True, "Capacity")

params = pywrapcp.DefaultRoutingSearchParameters()
params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GENERIC_TABU_SEARCH
params.time_limit.seconds = int(search_limit_seconds)
params.log_search = True
solution = routing.SolveWithParameters(params)
```

## Search And Extraction

- Use a constructive first-solution strategy that matches the structure of the problem, then a local-search metaheuristic for improvement.
- For large optional pickup-delivery or dial-a-ride style models, `AUTOMATIC` is a strong first-solution default, and `GENERIC_TABU_SEARCH` is often a good local-search metaheuristic for escaping local minima. Avoid assuming that simple arc-based constructors such as `PATH_CHEAPEST_ARC` will work well on heavily constrained optional-service instances.
- If the objective is mostly served-count based, give local search a secondary route-quality signal through the arc-cost evaluator, such as scaled travel time or travel-plus-service time. Keep skip penalties large enough that the secondary cost cannot outweigh serving one more job.
- If the task states a search or solver time limit, pass that limit to the OR-Tools search parameters and reserve time for extraction, auditing, and writing outputs. Do not silently expand the limit for solution quality.
- If no task-specific search limit is given but the benchmark has an outer wall-clock timeout, set an internal OR-Tools search limit well below that timeout and reserve time for data loading, extraction, independent auditing, and report writing. A common pattern is to spend about one third of the available agent time on search.
- Long OR-Tools searches can look idle to command runners. If a solve may run near a per-command idle timeout, enable lightweight progress output such as `search_parameters.log_search = True`, run Python unbuffered, or print flushed progress before and after the solve.
- Before starting another long solve, check that enough wall-clock time remains to finish the solve, extract the incumbent, audit the route sequence, and write the requested output. A lower-quality audited output is usually better than timing out with no final report.
- For long searches, consider collecting incumbent `NextVar`, route start/end cumul vars, and `CostVar`; keep the best collected solution by cost if the final return value is unavailable or inconvenient to extract.
- Extract routes by following `NextVar` from each vehicle start to end, then pass the ordered stops to an independent audit/reporting step.



## Implementation And Audit Checklist

Before solving, perform the following checks rather than relying on a solver status or plausible-looking route:

- Read the referenced data-convention file first. Confirm the meanings and units of node IDs, depot IDs, request IDs, pickup/dropoff records, travel entries, service times, time windows, shift menus, capacities, invalid-arc sentinels, objective priorities, and output fields.
- Assert that request counts, node counts, vehicle counts, record counts, and every row and column of each matrix agree. Reject missing, non-finite, negative, or otherwise malformed values unless the convention explicitly defines them. Convert all model quantities to integers before constructing callbacks, dimensions, ranges, or penalties.
- Maintain separate maps for external IDs, internal matrix nodes, manager nodes, and routing indices. Never use an external ID as a routing index without an explicit conversion through the manager.
- If vehicles have distinct shift starts, shift bounds, or depot copies, give each vehicle its own internal start and end depot node (or otherwise encode the distinction exactly). Set the corresponding start and end cumul ranges, allowed discrete starts, and span limits explicitly; do not assume a shared depot or fixed-zero start is equivalent.
- Define time transit consistently. If it is travel plus service at the departing node, interpret the cumul as arrival/service-start time and independently verify departure as arrival plus service. Set ordinary visit windows on the intended cumul, and separately verify waiting, service, travel, end time, and shift duration.
- Add a capacity dimension with the intended demand convention and no unintended slack. For pickup-and-delivery requests, enforce pickup and dropoff on the same vehicle, pickup-before-dropoff precedence, and load bounds; when a request is optional, make the pickup/dropoff pair jointly optional rather than allowing only one endpoint to disappear.
- Make forbidden travel arcs genuinely infeasible with explicit arc restrictions or equivalent constraints. A large cost may be an additional safeguard, but it must not be the sole mechanism that permits an invalid arc; reject any final route containing an invalid leg and guard against penalty overflow.
- Configure optional requests with penalties that reflect the stated primary objective. Ensure one additional served request dominates any secondary travel or duration tie-breaker, while retaining a useful positive arc-cost signal for route improvement.
- After solving, follow `NextVar` from every vehicle start through its end and record the ordered external stops, including the correct vehicle-specific start and end mapping. Independently recompute, from raw data rather than solver cumul values, every leg's validity and travel, each stop's waiting/service/arrival time, pickup/dropoff precedence, load progression and capacity, time-window membership, shift membership, route duration, distance, and served/skipped request status.
- Reconcile independently computed metrics with the report fields and objective claims. Reject or repair inconsistent routes, missing vehicles, unpaired requests, duplicate visits, impossible starts, invalid arcs, or schema/type violations. Write `/root/report.json` only after this audit and only in the task-required report schema.
