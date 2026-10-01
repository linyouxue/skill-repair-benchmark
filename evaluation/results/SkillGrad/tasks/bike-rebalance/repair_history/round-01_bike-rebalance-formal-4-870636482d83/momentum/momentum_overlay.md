### [bike-rebalance] missing required `report.json` output artifact
- signal: failure
- pattern: output-commit-report-json
- anchor: (none)
- gap: The run ended without executing a finalization step that writes the required `report.json` file. As a result, the output inventory is empty and the evaluator cannot check feasibility/objective at all.
- proposed_change: Add an explicit “OUTPUT COMMIT” step to an L2 workflow section (likely in `scip-opt` or a top-level solve-and-report workflow): (1) build full `report.json` conforming to schema, covering all vehicles and all stations; (2) validate JSON and key invariants; (3) write to `report.json`; (4) re-open and parse to confirm existence/validity; (5) only then terminate.

## WORKFLOW-THEMES

- (none this iteration)
