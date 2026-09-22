### [organize-messy-files] executor failed to perform the required create→classify→move→verify workflow; no target folders created/populated and most files left unorganized
- signal: failure
- pattern: workflow-must-complete-fixed-taxonomy-loop
- anchor: post-write-verification
- gap: Despite the L2 "Post-write verification" completion gate, the run appears to terminate after tool calls without executing the core organizing actions (create the 5 required directories with exact names; run a classify→move loop over all files; then re-inventory to assert zero leftovers). The end-state on disk shows the required subject folders (LLM, trapped_ion_and_qc, black_hole, DNA, music_history) are not created/populated, and only a few files are present under an unrelated "all/" directory—indicating either a no-op execution phase or an unverified/partial pass that failed the fixed-taxonomy requirements.
- proposed_change: Strengthen L2 file-organizer "Post-write verification" into a harder termination barrier for fixed-taxonomy tasks: (1) require creation of exact folder names before any classification; (2) add a "no-op guard" that compares pre/post inventories (file count outside target folders must drop to 0, not just "looks organized"); (3) explicitly require a final `find "$root" -maxdepth 1 -type f -print` (and/or equivalent for nested leftovers) and forbid end_turn if it prints anything. If recurrence persists, consider lifting the full fixed-taxonomy end-state assertion + iterative repair algorithm into a new L3 reference (e.g., references/fixed-taxonomy-completion-gate.md) and point to it from L2.

## WORKFLOW-THEMES

- (none this iteration)
