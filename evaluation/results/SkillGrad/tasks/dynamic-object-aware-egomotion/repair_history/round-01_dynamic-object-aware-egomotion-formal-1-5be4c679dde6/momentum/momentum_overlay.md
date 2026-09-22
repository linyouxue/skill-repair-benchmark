### [dynamic-object-aware-egomotion] missing required output artifacts (no `/root/pred_instructions.json` and no `/root/pred_dyn_masks.npz`)
- signal: failure
- pattern: deliverables-gate-always-write-artifacts
- anchor: output-validation
- gap: The run terminated without performing the mandatory serialization step: output inventory is empty, indicating the agent never wrote the two required deliverables. The current guidance has format checks, but lacks an explicit hard-stop rule that *forces* writing `/root/pred_instructions.json` and `/root/pred_dyn_masks.npz` and then verifying they exist and are loadable before ending.
- proposed_change: Update `output-validation` SKILL.md to include an explicit “deliverables gate”: (1) write both files unconditionally (even with empty masks, write valid empty CSR arrays for every sampled frame), (2) immediately re-open from disk and run the listed validations (existence, JSON parse, NPZ key coverage, CSR invariants), and (3) forbid termination until the gate passes. Also add a pointer to `sampling-and-indexing` for computing fps=5 sample indices and to `dyn-object-masks` for CSR key naming (`f_{i}_*`) so the gate can check exact expected keys.

## WORKFLOW-THEMES

- (none this iteration)
