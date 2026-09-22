### write-required-output-artifact | workflow | executor ends turn without writing the required deliverable file
- anchor: output-expectations
- appeared_in: iter_0, iter_1
- description: The executor completes analysis (or otherwise terminates normally) but fails to produce the required output artifact at the exact path expected by the harness, leaving the output inventory empty (e.g., missing `/app/output/oscillation_report.json`). This is a workflow finalization failure: even correct reasoning would not be graded because no deliverable is serialized. In iter_1, the trace showed only 3 tool calls total and none that created/wrote the required path; the agent terminated (“end_turn”) without any write/verify step.
- latest_executor_action: Treat deliverable-writing as a mandatory finalization step. Before ending: (1) create `/app/output` if needed, (2) write the required JSON to the exact required filename, (3) close/flush, and (4) verify existence + non-empty + JSON-parseable by reading it back or stat’ing it. Only then end the turn.
- remedy_log:
  - iter_0 | diagnosis: run terminated normally but never wrote the required `/app/output/oscillation_report.json`; output inventory empty
            | patch: (none yet) add an explicit “Output Expectations / Write required artifact” rule and end-of-run checklist under the skill’s output section
  - iter_1 | diagnosis: run never produced `/app/output/oscillation_report.json`; final agent message ended turn without any tool call that writes/verifies the output report
            | patch: (none yet) enforcement likely needs a stronger end-of-run checklist gate (e.g., “do not end turn until output exists and parses”) and/or a dedicated L3 write-and-verify algorithm referenced from L2
