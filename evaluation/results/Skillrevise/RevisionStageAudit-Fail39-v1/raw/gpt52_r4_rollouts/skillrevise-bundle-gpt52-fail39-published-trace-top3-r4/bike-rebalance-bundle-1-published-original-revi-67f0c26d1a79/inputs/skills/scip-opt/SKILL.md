# Robust Optimization Modeling (SCIP optional, contract-driven)

## Purpose
Produce a correct, verifier-aligned solution artifact for optimization-style tasks (objective + constraints), using PySCIPOpt/SCIP when available and a deterministic heuristic-with-repair fallback when it is not, with mandatory discovery and post-write validation.

## When to Use
Use this skill when the task describes an optimization problem (min/max objective with hard constraints, possibly with soft penalties) and the evaluation likely depends on a JSON (or similar) output artifact whose schema and internal consistency must match a validator.

## Procedure
- 1) Discover the environment contract (before modeling)
- List the working directory and locate: input files (often *.json), required output filename(s) mentioned in instructions/README, and any validator/tests (e.g., test_*.py, validate*.py, scripts).
- Open and parse the primary input file(s) as JSON.
- Extract and record a minimal contract snapshot used for later validation:
- required entity IDs (e.g., all stations/jobs/items),
- declared counts (e.g., vehicle_count),
- any bounds/capacities,
- required output path/name (if explicitly stated).
- Checkpoint: if the required output path/schema is not explicit, search for it in repo docs/tests; if still ambiguous, proceed but keep output validation derived from discovered input structure and any validator code found.
- 2) Validate inputs and assumptions (fail fast on non-recoverable issues)
- Assert input JSON parses; required top-level keys exist (as discovered); IDs are unique; numeric fields are finite numbers.
- If any key/field is missing or ambiguous, stop and request clarification only if the task interface allows; otherwise choose the least-committal interpretation and record it for validation.
- 3) Select solution method with a bounded fallback gate
- Try importing PySCIPOpt. If import succeeds, run a sanity optimization (tiny model) to confirm the backend works (optimize, status feasible/optimal, at least one solution).
- Decision:
- If PySCIPOpt works: use the solver path (step 4).
- If PySCIPOpt is missing/broken OR solver later yields no incumbent: use the heuristic + repair path (step 5).
- Constraint: do not install packages or assume system binaries unless the environment contract explicitly allows it.
- 4) Solver path (SCIP via PySCIPOpt), kept minimal and safe
- Build the smallest model that matches the discovered contract:
- decision variables for the required decisions (binary/integer/continuous),
- hard constraints for feasibility,
- explicit slack variables for any soft rules (no abs() on expressions).
- Set limits (time and optional gap) and suppress verbose output when allowed.
- Optimize and checkpoint:
- If model.getNSols() == 0, capture status and switch to step 5 (fallback) rather than failing.
- Otherwise extract solution values with numeric tolerances (e.g., binary > 0.5).
- Reconstruct key quantities outside the solver (objective components and each hard constraint LHS/RHS) for later validation.
- 5) Heuristic + repair fallback (deterministic, bounded)
- Construct an initial feasible (or near-feasible) solution using greedy rules grounded in the input:
- prioritize satisfying hard constraints first; treat soft penalties as tie-breakers.
- Add a bounded repair loop:
- detect violations (capacity, balance, coverage, route continuity, etc. as applicable),
- apply local fixes (swap, move, clamp, add slack/unmet variables),
- stop after a small fixed number of passes or when violations do not decrease.
- If strict feasibility is impossible due to input bounds, produce the best-effort solution that still respects non-negotiable format requirements, and represent unmet quantities via explicit slack/unmet fields if the contract/validator supports them; otherwise keep values within bounds and document shortfall in optional metadata fields only if allowed by schema discovery.
- 6) Build the output artifact from the solution (no assumptions about schema)
- Create the output JSON structure by following (in order of priority):
- explicit task instruction schema,
- discovered validator expectations (read validator code to learn required keys),
- pattern from any provided example output file,
- otherwise mirror input entity IDs with per-entity records plus an objective summary.
- Ensure ID coverage: every required ID from the input snapshot must appear exactly once where expected.
- Ensure internal consistency: totals equal sums over records; derived fields are recomputed from primitives (do not copy solver objective without reconstruction).
- 7) Post-write schema and consistency validation (mandatory final gate)
- Write the output JSON to the required path/name if specified; otherwise to the task-specified default if discovered; otherwise to a conservative default like report.json only if no other evidence exists.
- Reload the written file and validate:
- JSON parses,
- required top-level keys exist and have correct types,
- list lengths match declared counts (e.g., vehicle_count),
- all required IDs are present with no extras/duplicates,
- numeric fields are within discovered bounds (capacities, non-negativity, etc.),
- recomputed objective/totals match reported values within a small tolerance.
- If validation fails: fix the minimal issue and rewrite once (bounded). If it still fails, stop and surface the specific failing assertion and the discovered contract snapshot.

## Constraints / Pitfalls
- Never hard-require PySCIPOpt: if import, sanity solve, or optimization fails to produce an incumbent, you must switch to a bounded heuristic + repair path and still produce a valid artifact.
- Do not hard-code paths, schema keys, or counts unless they are explicitly stated in instructions or discovered from input/validator; always perform discovery preflight and a post-write reload validation before declaring completion.