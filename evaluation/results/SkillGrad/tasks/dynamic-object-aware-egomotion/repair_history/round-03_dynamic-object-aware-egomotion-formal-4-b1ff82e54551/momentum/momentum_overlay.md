### [dynamic-object-aware-egomotion] terminated without producing required `/root/pred_instructions.json` and `/root/pred_dyn_masks.npz`
- signal: failure
- pattern: deliverables-gate-always-write-artifacts
- anchor: output-validation
- gap: The executor ended the run (`end_turn`) without invoking any skills (`n_skill_invocations: 0`) and without running the output-validation “Deliverables gate (hard stop)”. As a result, neither required artifact was written to the mandated absolute `/root/...` paths, so the verifier’s output inventory contained only the input video. The mechanism is explicitly “terminate without pipeline + without write+re-open validation”.
- proposed_change: Strengthen the `output-validation` L2 “Deliverables gate (hard stop)” to be an explicit termination blocker: add a rule like “Never call `end_turn` until `validate_gate(...)` has been executed and passed against the on-disk `/root/pred_instructions.json` and `/root/pred_dyn_masks.npz`.” Add an early-step checklist pointer (or an L3 short algorithm) that forces: sampling/indexing → egomotion → dyn-mask generation → write JSON+NPZ → re-open/validate. Optionally add a preflight check that `/root` is writable and that the exact filenames are reserved before doing any analysis.

## WORKFLOW-THEMES

- (none this iteration)
