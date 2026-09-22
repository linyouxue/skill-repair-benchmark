### always-emit-required-artifact | workflow | always write /root/report.json in the required schema before terminating
- anchor: reporting-discipline
- appeared_in: iter_0
- description: The executor ends the turn without producing the required report artifact (e.g., /root/report.json), causing evaluation to fail regardless of schedule quality. The failure mode is a missing terminal-phase step: after (attempted) modeling/solving, the executor must always serialize a schedule to the mandated schema and write it to the required path. This includes a fallback behavior when optimization fails or is incomplete: emit a heuristic-feasible schedule with an explicit solver_status rather than emitting nothing.
- latest_executor_action: Treat output emission as mandatory. Before ending any run, perform a finalization checklist: (1) build arrays for every required resource×time field; (2) compute hourly_summary and summary totals from those arrays; (3) populate all required constraint_check keys; (4) write the JSON exactly to /root/report.json; (5) re-open the written file to confirm it exists and is valid JSON with required top-level keys. If MILP solve fails or has no incumbent, switch to a heuristic that produces a feasible schedule and still write the report with solver_status indicating heuristic/repair.
- remedy_log:
  - iter_0 | diagnosis: run ended (termination_reason: end_turn) with output inventory [] — no /root/report.json artifact was written
            | patch: (none yet; initial record)  
