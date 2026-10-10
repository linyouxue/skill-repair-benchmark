# civ6-map-placement-optimization

## Purpose
Executable workflow for Civ6-style placement optimization tasks: given a Civ6Map and a count of items to place, produce a validated placement set that maximizes total adjacency score, using the task family's provided libraries rather than ad hoc search.

## When to Use
Trigger when the task supplies a Civ6Map sqlite file (or equivalent tile dataset with terrain/feature/river fields) plus a scenario descriptor asking for N placements that maximize an adjacency-based objective, and the environment exposes a civ6lib-style helper package. Do not use for generic non-spatial optimization or when the verifier scores something other than adjacency sum.

## Procedure
- Discover: locate the scenario descriptor (e.g. scenario.json or task spec), the Civ6Map sqlite file, and any helper library directory (search for placement_rules and adjacency_rules modules). Record N, the objective, output path, and any center/range constraint. Checkpoint: print discovered file paths and callable names before coding.
- Validate inputs: open the sqlite map and read tile rows (plot id, terrain, feature, river, coordinates). Confirm that validate_placement and calculate_total_adjacency (or equivalents) are importable. If the helper library is missing, fall back to a minimal local scorer defined only from the scenario's documented adjacency rules; log that fallback is active.
- Prune and score: filter tiles to those passing validate_placement for a single item. For each surviving tile, compute an intrinsic score plus a potential-adjacency score from neighbors that also pass validation. Keep the top-K candidates (K small, e.g. 2N to 4N). Checkpoint: assert len(candidates) >= N; otherwise relax K or report infeasible.
- Anchor search with local swap: enumerate anchor options (either each top candidate, or each legal center position if a center/range constraint exists). For each anchor, greedily add the next placement that maximizes marginal calculate_total_adjacency subject to validate_placement and mutual-exclusion rules. Then run local search: repeatedly swap one placed tile with an unplaced candidate while the total strictly increases. Track best-so-far globally.
- Verify and emit: on the best solution, call validate_placement for every placement and recompute calculate_total_adjacency; assert the recomputed total equals the sum of per-placement contributions. Write the solution to the required output path in the schema the scenario specifies. If a time budget is exhausted mid-search, emit the current best-so-far instead of aborting.

## Constraints / Pitfalls
- Do not hardcode tile coordinates, scores, or N from any prior instance; always re-derive from the current map and scenario.
- Prefer civ6lib (or the task-provided helper) over reimplemented adjacency math; only use the fallback scorer when imports fail, and label the output as fallback-derived.
- Never return a solution that has not been revalidated end-to-end; a near-optimal unvalidated set is worse than a validated slightly smaller one.
- Keep anchor enumeration and local swap bounded (cap iterations) and always emit the best-so-far on interrupt or timeout rather than exiting empty.
- Avoid exhaustive O(M choose N) enumeration; rely on pruning + anchor + local swap as the primary method.