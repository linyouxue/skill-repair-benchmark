### [lab-unit-harmonization] required harmonized CSV was never written before termination
- signal: failure
- pattern: persist-required-deliverables
- anchor: step-4-persist-deliverable-post-save-verification
- gap: The run terminated (end_turn) without executing the Step 4 hard completion gate: no `df.to_csv(out_path, index=False)` to the required path, no `Path.exists()/stat().st_size` check, and no round-trip reload to confirm schema. The observable outcome is an output inventory containing only the two input CSVs.
- proposed_change: Strengthen the executor’s termination policy at anchor `step-4-persist-deliverable-post-save-verification` so Step 4 is treated as a non-skippable pre-end_turn checklist item (explicitly: “if required output path does not exist and re-load cleanly, you are not allowed to end”). Consider adding a conspicuous, last-line “STOP CONDITION” statement in SKILL Step 4: “Do not call end_turn until the output file exists at the exact required path and round-trips.”

## WORKFLOW-THEMES

- (none this iteration)
