### [lab-unit-harmonization] missing required harmonized CSV at specified output path (terminated before Step 4 hard gate)
- signal: failure
- pattern: persist-required-deliverables
- anchor: step-4-persist-deliverable-post-save-verification
- gap: The run ended (end_turn) without executing the mandatory completion gate in SKILL.md Step 4 (“Persist Deliverable + Post-save Verification”). Concretely: no `df.to_csv(out_path, index=False)` to the exact required path, and no post-save assertions (`out_path.exists()`, `st_size > 0`, round-trip `pd.read_csv` schema/order check). This leaves the verifier with no artifact to assess formatting/unit-range requirements.
- proposed_change: Strengthen the executor’s termination policy at anchor `step-4-persist-deliverable-post-save-verification` so it is impossible to end the run without an explicit, immediately-pre-terminal checklist execution: (1) print/echo the exact output_path, (2) write file, (3) verify exists + non-empty, (4) reload and assert columns/order, and (5) only then allow end_turn. If the agent is about to end without having executed this block, it should instead resume and perform Step 4.

## WORKFLOW-THEMES

- (none this iteration)
