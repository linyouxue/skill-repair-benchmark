# Civ6 District Placement and Adjacency Optimizer Workflow (civ6lib-driven)

## Purpose
Provide a reusable, execution-first procedure to load a Civ6 scenario/map, generate legal district placements, optimize an objective (typically adjacency-based), and emit a verifier-aligned JSON artifact using in-repo legality and scoring code rather than memorized game rules.

## When to Use
Use this skill when a task requires computing or optimizing Civilization 6 district placements (city center plus districts) under placement legality and adjacency/scoring rules, especially when inputs are files (scenario JSON, Civ6Map, etc.) and the output must be a machine-checked JSON.

## Procedure
- 1) Discover the contract (inputs, output path, schema, objective)
- Read the task instructions first; extract: required output path, required JSON keys, and objective (maximize total adjacency, meet target, etc.). If any are missing, mark them as unknown and plan to discover via repo files.
- Execution anchor: list the repo root and locate task-provided config (often scenario.json) and any validator script/README that names the output path and schema.
- Checkpoint: you can cite (a) the exact input file paths and (b) the exact output path and JSON shape source. If still unknown, do not start a large search; proceed to step 2 to find the authoritative checker.
- 2) Ground in the environment (find the authoritative code paths)
- Locate civ6lib (or equivalent in-repo modules) by searching for files named placement_rules.py / adjacency_rules.py (or imports referencing PlacementRules / AdjacencyCalculator).
- Do not assume hard-coded import roots (e.g., src.*). Instead, add the discovered directory to PYTHONPATH/sys.path in your driver script.
- If a map parser exists, identify it by searching for references to Civ6Map, sqlite, or map loading in the repo.
- Fallback (bounded): if you cannot locate placement/scoring modules within a small, targeted search (e.g., search by filenames and class names only), stop and request the missing location/entrypoint rather than running broad filesystem greps.
- 3) Validate minimal end-to-end hooks before optimization (small sanity run)
- Write/run a tiny driver that:
- Loads the scenario/config.
- Loads/parses the map into the tile representation expected by civ6lib (Tile objects or equivalent).
- Instantiates PlacementRules (via get_placement_rules if available) and AdjacencyCalculator (via get_adjacency_calculator if available).
- Execution anchor: call validate_placement for 1-2 candidate placements and call the adjacency/scoring function on a tiny placement set; ensure you get structured validity and numeric scores without exceptions.
- Checkpoint: you have confirmed (a) legality can be queried from code and (b) score can be computed from code. If either fails, fix imports/parsing before proceeding.
- 4) Build candidate sets using validators (not manual rule tables)
- Enumerate candidate city centers only if required by the task; otherwise use the provided city center(s).
- For each district type required by the task:
- Generate candidate tiles by iterating the map tiles in a bounded radius relevant to the validator (do not assume a fixed radius unless the validator enforces it; prefer using the validator to decide).
- Filter candidates by calling PlacementRules.validate_placement(district_type, x, y, context) with the minimal required context (existing placements, population, etc.).
- Checkpoint: for each district, you have a candidate list size and can explain why candidates are legal (because validate_placement returned valid).
- 5) Define the optimization objective and state transition
- Objective: use the repo-provided adjacency/scoring calculator as the primary scoring function. If the task requires a different objective, compose it explicitly from verifier-visible requirements.
- State: represent a partial placement (already placed districts and consumed tiles). When simulating a placement, update the simulated map state if features/resources are destroyed by placing a district, then recompute score using the calculator on the simulated state.
- Checkpoint: scoring a partial solution is deterministic and derived from the same code used for final verification.
- 6) Run a bounded search with pruning (avoid brute-force explosions)
- Choose a search strategy based on candidate sizes:
- Small product space: backtracking with branch-and-bound.
- Large space: greedy + local improvement (swap/move), or beam search with fixed beam width.
- Always enforce hard bounds: max states expanded, max wall-clock time, and/or max depth expansions per district.
- Pruning rules (validator-driven):
- Immediately reject moves that violate validate_placement given the current partial placements.
- Use an optimistic upper bound (e.g., current score + sum of best remaining single-district scores) to prune branches that cannot beat the incumbent.
- Decision point: if bounds are hit before convergence, return the best-so-far solution and record that the result is bounded/approximate (unless the task requires optimality).
- 7) Emit the required JSON and verify it against the same code paths
- Serialize placements exactly to the task-specified JSON schema (keys, coordinate format, district identifiers). Do not invent fields; if schema is unclear, discover it from checker scripts/examples.
- Execution anchor: after writing, re-open the file, parse JSON, reconstruct placements, and re-run:
- validate_placement for each placement (and any global constraints like uniqueness/limits if exposed by the library), and
- adjacency/scoring to confirm the reported score matches.
- Checkpoint: file exists at the task-required output path; JSON parses; all placements validate; computed score matches.

## Constraints / Pitfalls
- Never hard-code repo paths, import roots, map formats, or rule tables. Treat placement legality and adjacency as code-defined; use validators/calculators as the authority and add discovery steps when modules are not found.
- Do not run unbounded filesystem searches or unbounded combinatorial searches. Require explicit caps (time/states) and a fallback strategy (greedy/beam) when the search space is too large or tools/parsers are missing.