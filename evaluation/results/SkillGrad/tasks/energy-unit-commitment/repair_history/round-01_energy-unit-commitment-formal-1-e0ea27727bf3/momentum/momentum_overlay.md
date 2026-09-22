### [energy-unit-commitment] missing required /root/report.json output artifact
- signal: failure
- pattern: always-emit-required-artifact
- anchor: reporting-discipline
- gap: The run terminated (termination_reason: end_turn) without any output artifacts (output inventory: []). The workflow lacks (or failed to execute) a terminal “serialize schedule to required schema and write /root/report.json” step.
- proposed_change: Update MILP solver workflow L2 to include a mandatory finalization checklist with a hard stop: “Do not end until /root/report.json exists and passes a minimal schema check (required keys, correct array lengths).” Include explicit fallback: if solver has no incumbent or returns infeasible, still construct a heuristic-feasible schedule and write it with solver_status: heuristic_feasible.

## WORKFLOW-THEMES

- (none this iteration)
