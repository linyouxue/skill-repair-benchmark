### [enterprise-information-search] missing required output file `/root/answer.json`
- signal: failure
- pattern: output-artifact-finalization-gate
- anchor: (none)
- gap: The rollout terminated (“end_turn”) after many internal steps but never executed the persist/finalize step. No file-write occurred, so the output inventory is empty. The current skill focuses on retrieval/extraction correctness (product grounding, reviewer extraction) but lacks a hard workflow checkpoint: “before terminating, write `/root/answer.json` in the required schema and read it back to validate.”
- proposed_change: Add an L2 section to SKILL.md (new H2, e.g., “Finalize: write answer.json + verify schema”) that defines an explicit completion gate. Include: required path, required q-key coverage, per-question object shape, invariant “answer is list”, and a mandatory read-back validation step; instruct executor to refuse termination until the gate passes.

## WORKFLOW-THEMES

- (none this iteration)
