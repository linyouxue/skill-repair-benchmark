### [sec-financial-report] Missing required output artifact (/root/answers.json)
- signal: failure
- pattern: required-artifact-answers-json
- anchor: (none)
- gap: Agent ended at finalization/end_turn without creating the mandated output file. The verifier expects a JSON artifact at `/root/answers.json` (with keys like `q1_answer..q4_answer`), but the output inventory was empty.
- proposed_change: Add a workflow-level “required-artifact completion” rule (new L2 section) that forces: write `/root/answers.json` in the exact schema, then re-open/read-back to validate JSON parse + key set before termination.

## WORKFLOW-THEMES

- (none this iteration)
