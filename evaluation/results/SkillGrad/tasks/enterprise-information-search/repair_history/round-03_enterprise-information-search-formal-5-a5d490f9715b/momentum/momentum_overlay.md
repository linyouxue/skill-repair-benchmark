### [enterprise-information-search] Missing required output artifact: `/root/answer.json` not written/validated before termination
- signal: failure
- pattern: output-artifact-finalization-gate
- anchor: finalize-required-write-root-answer-json-validate-before-terminating
- gap: Agent terminated with “end_turn” without producing any `/root/answer.json` artifact; it did not execute the skill’s “Finalize (Required): hard completion gate (block termination)” (write → read-back → schema validate). Diagnosis notes `n_skill_invocations: 0`, indicating the executor never entered the skill flow that contains the gate.
- proposed_change: Strengthen the L2 finalize section to be unconditional on skill invocation: add an explicit rule like “Even if you did not use this skill for retrieval, you MUST run this finalize gate before ending any run.” Also consider adding a short top-of-file termination checklist that points to `references/finalize_answer_json.md` for the write_and_verify procedure.

## WORKFLOW-THEMES

- (none this iteration)
