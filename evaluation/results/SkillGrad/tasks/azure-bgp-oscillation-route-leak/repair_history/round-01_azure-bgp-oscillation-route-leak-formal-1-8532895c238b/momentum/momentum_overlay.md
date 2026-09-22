### [azure-bgp-oscillation-route-leak] missing required output artifact (`/app/output/oscillation_report.json`)
- signal: failure
- pattern: write-required-output-artifact | new
- anchor: output-expectations
- gap: The run ends with `termination_reason: end_turn` and `execution_ok: true` but never performs the finalization/write step; no output files are present, so the verifier cannot validate anything. The current skill’s “Output Expectations” describes what a correct solution should contain, but it does not enforce an explicit mandatory file-write to the harness-specified path.
- proposed_change: Update L2 `## Output Expectations` to include an explicit, non-optional deliverable rule: “Always write `/app/output/oscillation_report.json` (create dir if needed) before ending.” Add a short end-of-run checklist: write → flush/close → read-back/JSON-parse sanity check → confirm file exists & non-empty.

## WORKFLOW-THEMES

- (none this iteration)
