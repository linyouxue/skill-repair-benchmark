### [sec-financial-report] missing required /root/answers.json artifact (q1_answer..q4_answer)
- signal: failure
- pattern: required-artifact-answers-json
- anchor: plan-package-outputs
- gap: Agent terminated (`end_turn`) after tool executions without producing `/root/answers.json`. Specifically, it did not perform the mandated gating sequence “write answers.json → read back/parse → schema/key check → existence check” immediately before termination, despite the skill’s Plan & Package Outputs rule and the provided `write_verify_and_gate` snippet.
- proposed_change: No new capability needed; strengthen enforcement. Patch L2 `## Plan & Package Outputs` to include an explicit pre-`end_turn` checklist bullet that must be executed verbatim for `/root/answers.json` tasks (write → parse → assert key set → assert exists). Optionally add a short “Termination is forbidden until gate passes” reminder line in Common Pitfalls.

## WORKFLOW-THEMES

- (none this iteration)
