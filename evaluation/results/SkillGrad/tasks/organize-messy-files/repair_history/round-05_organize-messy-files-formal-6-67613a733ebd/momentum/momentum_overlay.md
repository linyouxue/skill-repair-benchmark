### [organize-messy-files] Skipped core file organization; ended with no subject folders created/populated and no moves performed
- signal: failure
- pattern: workflow-must-complete-fixed-taxonomy-loop
- anchor: post-write-verification
- gap: The executor terminated without executing the required fixed-taxonomy loop (create exact folders → inventory → classify → move every file → end-state assertion). Evidence: no `LLM/`, `trapped_ion_and_qc/`, `black_hole/`, `DNA/`, or `music_history/` directories populated; output inventory still shows files in `papers/all/...`; run metadata notes `n_skill_invocations: 0`, consistent with a no-op/early-stop despite the task requiring on-disk mutations.
- proposed_change: Strengthen/clarify the L2 completion gate at `post-write-verification` to include an explicit **no-op guard** tied to termination: before end_turn, assert (a) required folders exist, (b) at least one batch of mkdir/mv actions was executed (or move-log non-empty), and (c) leftovers check is empty (no files outside target folders anywhere in scope). If any check fails—including “0 skill invocations / 0 mutations”—the executor must continue with classify→move rather than stop; consider adding a pointer that fixed-taxonomy tasks should immediately trigger `references/fixed-taxonomy-completion-gate.md`.

## WORKFLOW-THEMES

- (none this iteration)
