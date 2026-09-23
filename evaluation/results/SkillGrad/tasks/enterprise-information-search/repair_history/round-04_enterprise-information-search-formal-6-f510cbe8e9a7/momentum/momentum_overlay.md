### [enterprise-information-search] Missing required output artifact: `/root/answer.json` not produced/validated
- signal: failure
- pattern: output-artifact-finalization-gate
- anchor: finalize-required-write-root-answer-json-validate-before-terminating
- gap: The run terminates (`termination_reason: end_turn`) without executing the skill’s mandatory completion routine. Concretely, there is no “write → read-back → schema validate” step and the required deliverable `/root/answer.json` is not created. Diagnosis notes the skill already contains an explicit "Finalize (Required): hard completion gate (block termination)" and that the run shows **0 skill invocations**, so the gate was never triggered.
- proposed_change: Strengthen the L2 termination-stop mechanism to be harder to skip even when the skill is not otherwise invoked: (a) add a highly salient, repeated one-liner checklist at the very top of SKILL.md (and/or immediately before the finalize section) like “BEFORE END_TURN: write + read-back-validate `/root/answer.json`”, (b) change the decision rule so `references/finalize_answer_json.md` is consulted by default for this benchmark (not only for multi-question/prior failures), and (c) if the framework supports it, add an explicit “on every task: run finalize gate” pointer in the earliest routing section.

## WORKFLOW-THEMES

- (none this iteration)
