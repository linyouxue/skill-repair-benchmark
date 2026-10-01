### [bike-rebalance] missing required output artifact `report.json`
- signal: failure
- pattern: output-commit-report-json
- anchor: output-commit-write-the-deliverable
- gap: The run terminated (`termination_reason: end_turn`) without executing the explicit deliverable commit phase required by `scip-opt` → “Output Commit (Write The Deliverable)”. Output inventory contains only `data.json`; there is no `report.json` write step and no post-write readback/parse validation.
- proposed_change: Reinforce `scip-opt` L2 `output-commit-write-the-deliverable` as a mandatory finalization checklist gate: always (1) assemble full `report.json` payload, (2) run completeness checks (required top-level keys; all vehicles/stations represented), (3) write `report.json`, then (4) immediately read back and validate JSON + required keys/entities using the branched scaffold in `scip-opt/references/output-commit-report-json.md`. Add a self-reminder to never `end_turn` until the readback check passes.

## WORKFLOW-THEMES

- (none this iteration)
