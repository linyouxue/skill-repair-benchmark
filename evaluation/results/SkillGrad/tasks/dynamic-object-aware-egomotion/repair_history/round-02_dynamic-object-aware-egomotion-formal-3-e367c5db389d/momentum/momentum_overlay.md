### [dynamic-object-aware-egomotion] terminated with no required artifacts (JSON + NPZ) written
- signal: failure
- pattern: deliverables-gate-always-write-artifacts
- anchor: output-validation
- gap: The run ended (“end_turn”) without invoking any of the pipeline skills (sampling-and-indexing, egomotion-estimation, dyn-object-masks) and without running the output-validation deliverables gate. Concretely, neither `/root/pred_instructions.json` nor `/root/pred_dyn_masks.npz` exists in the output inventory.
- proposed_change: Strengthen `output-validation`’s “Deliverables gate (hard stop)” to explicitly forbid termination until (a) the two files exist at the required absolute paths and (b) they have been re-opened from disk and validated. Add a short checklist-style instruction like: “Before end_turn: run sampling-and-indexing → egomotion-estimation → dyn-object-masks → write JSON/NPZ → run deliverables-gate validation; if any step wasn’t executed, do not terminate.”

## WORKFLOW-THEMES

- (none this iteration)
