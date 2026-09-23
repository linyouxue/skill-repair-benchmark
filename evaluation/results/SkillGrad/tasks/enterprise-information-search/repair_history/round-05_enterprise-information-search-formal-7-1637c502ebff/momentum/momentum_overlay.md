### [enterprise-information-search] Missing required `/root/answer.json` output artifact (no write + schema validation before termination)
- signal: failure
- pattern: output-artifact-finalization-gate
- anchor: finalize-required-write-root-answer-json-validate-before-terminating
- gap: Despite an explicit L2 hard-stop rule ("BEFORE `end_turn`: write `/root/answer.json` then read-back + schema-validate it." and "This gate is mandatory even if you never invoked the skill"), the run terminated at `end_turn` without any step that wrote the required file. The failure mode matches the recurrence signature: 0 effective skill invocation / skipped completion gate, so the grader found no artifact to evaluate.
- proposed_change: Make the completion gate harder to skip by adding an even-more-salient termination sentinel in L2: a top-of-file, single-line imperative + a short 3-step checklist that explicitly names the action types to execute ("run python to write file" or "use write_file tool") and a mandatory read-back assertion. Optionally add a rule that the *final assistant message* must state "WROTE /root/answer.json and read-back validated" to self-enforce the gate; keep the canonical algorithm in `references/finalize_answer_json.md`.

## WORKFLOW-THEMES

- (none this iteration)
