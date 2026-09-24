---
name: geospatial-routing-data
description: Handle depot/station coordinates, ID↔index mapping, great-circle distance
  (radius 3960.0 miles), and travel-distance reconstruction/validation for reported
  routes.
---

## Steps
1. Load `/root/data.json` and build explicit `station_id ↔ internal_index` maps; never assume IDs are contiguous.
2. Parse and sanity-check `latitude/longitude` ranges for depot and every station.
3. Implement great-circle distance exactly as specified (Earth radius `3960.0`) and clamp the cosine term to `[-1, 1]` to avoid FP domain errors.
4. Build routing nodes with explicit depot labels:
   - `START="depot_start"`, `END="depot_end"`
   - Internal station nodes are indices `0..n-1`, but reports must use original station IDs.
5. Build the distance matrix only over arcs actually allowed by the model (often exclude `START→END` if vehicles must visit ≥1 station).
6. For any produced `report.json`, recompute total travel distance by summing great-circle distances along each vehicle’s reported `route` (after converting station IDs back to indices) and compare to `summary.travel_distance_miles` within tolerance.
7. Validate basic route structure from the report:
   - starts with `depot_start`, ends with `depot_end`
   - contains ≥1 station (if required)
   - no station repeats within a vehicle route
   - stops list matches the non-depot nodes in the route (same order/length)
## Expected Result
Distances and route reconstructions match the task’s great-circle metric (radius 3960.0), and reported routes can be validated against coordinates with consistent ID/index handling.
