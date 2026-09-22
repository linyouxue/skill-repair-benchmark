### [dynamic-object-aware-egomotion] terminated without required JSON+NPZ deliverables on disk
- signal: failure
- pattern: deliverables-gate-always-write-artifacts
- anchor: output-validation
- gap: The agent performed `end_turn` without running the output-validation Deliverables gate: the output inventory contained only `input.mp4`, and neither `/root/pred_instructions.json` nor `/root/pred_dyn_masks.npz` was created. This indicates the mandatory pre-termination routine (write artifacts → reload from disk → validate invariants) was skipped entirely.
- proposed_change: Strengthen the output-validation anchor with an explicit termination interlock: immediately before any `end_turn`, assert both absolute paths exist and are loadable; if not, run `references/deliverables-gate.md` end-to-end (sampling → write JSON/NPZ → reload+validate) and only then terminate.

## WORKFLOW-THEMES
- (none this iteration)
