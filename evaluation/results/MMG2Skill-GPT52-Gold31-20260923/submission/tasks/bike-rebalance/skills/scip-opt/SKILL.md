---
name: scip-opt
description: Build, solve, and extract/validate MIP models in PySCIPOpt for routing/rebalancing
  problems, including penalties for unmet targets.
---

## Steps
1. Confirm PySCIPOpt is importable before modeling:
   ```python
   from pyscipopt import Model, quicksum
   ```
2. Create the model, define variables (binary arcs, integer loads/services, nonnegative unmet slacks), and add constraints (routing + subtour elimination + load/inventory feasibility + unmet linearization).
3. Set objective as “travel distance + penalty_weight * total_unmet”.
4. Set practical solve limits (time and/or mip gap), optimize, and require at least one incumbent (`model.getNSols() > 0`) before extracting.
5. Extract solution values using `model.getVal(var)` with a clear selection threshold for binaries (e.g., `> 0.5`).
6. Write output to `/root/report.json` matching the required schema:
   - include **all** `vehicle_count` vehicles and **all** stations from `data.json`
   - routes use `["depot_start", <station_id...>, "depot_end"]`
7. Independently validate the produced JSON *outside* SCIP:
   - recompute travel distance from coordinates (radius 3960.0)
   - recompute station totals, unmet amounts, penalty, and objective
   - check all stated hard rules (single-visit-per-vehicle, load propagation/capacity, inventory bounds, no pickup+drop at same stop, vehicles must visit ≥1 station)
## Expected Result
A valid `/root/report.json` whose summary/objective fields exactly match independent recomputation and whose routes/operations satisfy all hard constraints, with any unavoidable shortfalls captured via the unmet-penalty mechanism.
