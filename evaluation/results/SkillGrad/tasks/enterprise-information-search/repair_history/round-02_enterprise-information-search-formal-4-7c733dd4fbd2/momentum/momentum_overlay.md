### [enterprise-information-search] missing required `/root/answer.json` write despite finalize rule existing
- signal: failure
- pattern: output-artifact-finalization-gate
- anchor: finalize-required-write-root-answer-json-validate-before-terminating
- gap: The run terminated without creating `/root/answer.json` or any answer artifact. The last agent termination step occurred before any "finalize/write + read-back validation" action. Diagnosis notes 0 skill invocations, so the existing L2 completion gate ("Finalize (Required): write `/root/answer.json` + validate before terminating") was not applied.
- proposed_change: Reinforce the L2 finalize section as a non-optional pre-termination checkpoint: add an explicit directive to *block termination* until (a) `/root/answer.json` exists at the exact path, (b) it can be parsed as JSON, and (c) schema/key coverage checks pass. Add/keep a pointer to `references/finalize_answer_json.md` with a trigger like: "If multiple questions OR any prior run ended without a file-write, read and follow finalize_answer_json.md verbatim." Consider adding a brief self-reminder in the main workflow: "Before end_turn: run completion gate."

## WORKFLOW-THEMES

- (none this iteration)
