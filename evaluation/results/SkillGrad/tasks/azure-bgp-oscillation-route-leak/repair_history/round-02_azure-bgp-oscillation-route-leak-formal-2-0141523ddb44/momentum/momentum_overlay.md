### [azure-bgp-oscillation-route-leak] Missing required deliverable `/app/output/oscillation_report.json`
- signal: failure
- pattern: write-required-output-artifact
- anchor: output-expectations
- gap: The run terminated (“end_turn”) without performing the mandatory output-finalization step described in the skill’s **Output Expectations** section (“Always write the required deliverable file before ending the run … read it back to confirm it exists, is non-empty, and is valid JSON.”). The trace summary reports only 3 tool calls and none that create/write/verify `/app/output/oscillation_report.json`.
- proposed_change: Strengthen the L2 `## Output Expectations` checklist into a hard gate the executor cannot skip: add an explicit last-step instruction like “Do not call end_turn until you have written `/app/output/oscillation_report.json` and verified `json.loads(read_text())` succeeds and file size > 0.” If recurrence continues, fan-out to an L3 reference (e.g., `references/write-and-verify-output-json.md`) with a concrete, copy/pasteable algorithm and a self-check command sequence.

## WORKFLOW-THEMES

- (none this iteration)
