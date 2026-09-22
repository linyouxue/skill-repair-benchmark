### [dynamic-object-aware-egomotion] premature termination without required artifacts on disk
- signal: failure
- pattern: deliverables-gate-always-write-artifacts
- anchor: output-validation
- gap: The executor ended the turn without executing/enforcing the output-validation “Deliverables gate (hard stop)”. The workspace inventory contained only `input.mp4`; neither `/root/pred_instructions.json` nor `/root/pred_dyn_masks.npz` was created, meaning the mandatory write + re-open + validate loop never ran (or was not used as a termination blocker).
- proposed_change: Strengthen the L2 output-validation “Deliverables gate” to explicitly require a dedicated pre-`end_turn` step that (a) prints the two absolute required paths, (b) runs the full pipeline (sampling/indexing → egomotion → dyn masks → writers), and (c) performs an on-disk reload validation; forbid `end_turn` unless that step has executed and passed. If repeated recurrence continues, promote the termination blocker into a short L3 “termination-control” algorithm that the executor must follow whenever a grader expects fixed-path artifacts.

## WORKFLOW-THEMES

- (none this iteration)
