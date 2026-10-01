### output-commit-report-json | workflow | always emit required report.json deliverable before terminating
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor sometimes reaches the end of a task without creating the required output artifact (here: `report.json`). This is an earliest-failure class: the verifier cannot even begin feasibility/objective checks because the output inventory is empty. This is distinct from “wrong schema” or “infeasible solution”: nothing is written at all.
- latest_executor_action: Treat writing the deliverable as a mandatory final phase (“output commit”). Before ending: (1) assemble a complete `report.json` that includes all required top-level keys and required per-vehicle/per-station fields; (2) run internal consistency checks (schema presence, every vehicle present, every station present, route starts/ends at depot, no illegal stop semantics, objective recomputation); (3) write `report.json` to disk; (4) immediately re-open and parse it to confirm it exists and is valid JSON.
- remedy_log:
  - iter_0 | diagnosis: no `report.json` was produced; output inventory empty so grading fails on missing deliverable
            | patch: (none yet; to be added) output-commit rule in L2 (likely in optimization/reporting workflow)
