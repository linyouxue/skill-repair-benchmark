### [bike-rebalance] missing required `report.json` deliverable
- signal: failure
- pattern: output-commit-report-json
- anchor: output-commit-write-the-deliverable
- gap: The run ended (`termination_reason: end_turn`) without writing `report.json`; output inventory contains only `data.json`. The executor did not execute the “Output Commit (Write The Deliverable)” hard-gate behavior (assemble payload → write `report.json` → read back/parse → validate required keys/entities) before terminating.
- proposed_change: Strengthen the L2 `scip-opt` section `output-commit-write-the-deliverable` to be a stop-the-line checklist immediately before termination (explicit instruction: “Do not call end_turn until `Path('report.json').exists()` AND `json.loads` succeeds AND required keys check passes”). Also add an early plan marker at the top of SCIP workflow (“reserve last step for output commit; never skip even if solving fails—emit a structurally valid `report.json` with explicit failure fields”).

## WORKFLOW-THEMES

- (none this iteration)
