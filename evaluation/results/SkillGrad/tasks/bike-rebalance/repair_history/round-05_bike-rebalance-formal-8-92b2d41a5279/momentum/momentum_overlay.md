### [bike-rebalance] Missing required output file (`report.json` not produced)
- signal: failure
- pattern: output-commit-report-json
- anchor: output-commit-write-the-deliverable
- gap: The run terminated (`termination_reason: end_turn`) without executing the mandatory output-commit phase. The workspace output inventory contained only `data.json`, so the grader could not evaluate schema/feasibility/objective. This indicates the executor is not treating “write `report.json` + readback validation” as a hard termination gate.
- proposed_change: Strengthen the existing L2 anchor `output-commit-write-the-deliverable` into an explicit stop-the-line checklist that must run even when optimization/modeling is incomplete. Add a fallback branch: if the solver/model is not ready or no incumbent exists, still assemble a minimal structurally valid `report.json` (all vehicles/stations present, empty routes, zero transfers, correct numeric types) and then commit it using the write+readback + required-keys/entity-coverage checks from `scip-opt/references/output-commit-report-json.md`.

## WORKFLOW-THEMES

- (none this iteration)
