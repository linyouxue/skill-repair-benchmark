### [azure-bgp-oscillation-route-leak] Missing required deliverable JSON at `/app/output/oscillation_report.json`
- signal: failure
- pattern: write-required-output-artifact
- anchor: output-expectations
- gap: Despite an existing L2 hard gate (“write the required deliverable JSON to the exact harness path and verify it by reading it back”) plus an L3 algorithm (`references/write-and-verify-output-json.md`), the agent still ended the run ("termination_reason": "end_turn") without performing any write/verify action; the output inventory contained no `/app/output/oscillation_report.json`.
- proposed_change: In L2 `## Output Expectations`, make the hard gate an explicit *end-of-run checklist* with a stop condition (“DO NOT end turn until `verify_required_json(...)` succeeds”), and require the final assistant/tool step to (a) call the write routine, (b) read the file back, and (c) explicitly confirm verification passed. If this is already present, add a prominent reminder near the top-level workflow (“finalize: write+verify artifact”) and/or a short templated snippet showing the exact `/app/output/oscillation_report.json` path.

## WORKFLOW-THEMES

- (none this iteration)
