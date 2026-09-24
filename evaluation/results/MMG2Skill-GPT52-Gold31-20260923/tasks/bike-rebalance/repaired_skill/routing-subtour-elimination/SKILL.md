---
name: routing-subtour-elimination
description: Prevent disconnected station-only cycles in VRP/TSP-style MIPs that use
  binary arc variables.
---

## Steps
1. After adding depot start/end, continuity, and per-station out-degree ≤ 1 constraints, assume subtours are still possible.
2. Add one subtour-elimination method (pick one appropriate for size/complexity):
   - MTZ order constraints (compact, good default for small/medium instances), or
   - single-commodity connectivity flow (stronger, more memory), or
   - iterative DFJ cut separation (strong, more moving parts).
3. If using MTZ:
   - create `order[v,i]` for each vehicle and station
   - add `order[v,i] - order[v,j] + n*x[v,i,j] ≤ n-1` for all station pairs `i≠j`.
4. After solving, reconstruct each vehicle’s route by following its selected outgoing arcs from `depot_start` until `depot_end`; fail fast if:
   - a station cycle is detected,
   - the path is disconnected,
   - multiple outgoing arcs exist from one node.
## Expected Result
Each vehicle’s selected arcs form exactly one connected depot_start→…→depot_end path with no disconnected subtours.
