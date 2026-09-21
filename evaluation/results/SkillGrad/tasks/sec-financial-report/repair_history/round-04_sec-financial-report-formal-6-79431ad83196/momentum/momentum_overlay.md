### [sec-financial-report] missing required /root/answers.json artifact due to skipped pre-termination gate
- signal: failure
- pattern: required-artifact-answers-json
- anchor: plan-package-outputs
- gap: Agent reached the final termination step (`end_turn`) without running the mandated “write `/root/answers.json` → re-open & JSON-parse → assert exact required key set (no missing/extra) → assert file exists at absolute path” gate. This is explicitly required by the L2 section “Plan & Package Outputs” in both loaded skills, but the agent did not execute it.
- proposed_change: Strengthen the L2 hard-stop language under `plan-package-outputs` to be even harder to bypass: add a terminal sentinel instruction such as “If you are about to `end_turn`, you MUST first call/write `write_verify_and_gate('/root/answers.json', payload, required_keys)` when the prompt mandates answers.json; do not rely on memory.” If recurring despite this, add a dedicated L3 reference that includes a literal pre-`end_turn` micro-checklist the executor must copy verbatim.

## WORKFLOW-THEMES

- (none this iteration)
