### [azure-bgp-oscillation-route-leak] Missing required deliverable `/app/output/oscillation_report.json` due to premature termination
- signal: failure
- pattern: write-required-output-artifact
- anchor: output-expectations
- gap: Despite an explicit L2 hard gate (“Termination guard (must pass before ending the run): deliverable write + read-back verification”) and an L3 runnable algorithm (`references/write-and-verify-output-json.md`), the agent still ended the run (`end_turn`) without any tool call that writes `/app/output/oscillation_report.json` or reads it back to verify JSON parse + required keys.
- proposed_change: Strengthen enforcement at `output-expectations` so it is harder to “skip past” at runtime: require the executor to emit the filled pre-termination template immediately before ending (including the exact deliverable path and yes/no checks), and explicitly instruct: “If you have not just executed write_required_json(...) and verify_required_json(...), do not call end_turn.” If recurrence continues, add a more forceful L2 rule to treat any attempt to end without the filled template as an error state (self-interrupt and perform the write/verify steps).

## WORKFLOW-THEMES

- (none this iteration)
