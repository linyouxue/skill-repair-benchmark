### [lab-unit-harmonization] Missing deliverable file written
- signal: failure
- pattern: persist-required-deliverables
- anchor: step-4-persist-deliverable-post-save-verification
- gap: Executor terminated without creating the required output artifact `/root/ckd_lab_data_harmonized.csv`. The run skipped the hard completion gate described in SKILL.md Step 4 (“Persist Deliverable + Post-save Verification (STOP CONDITION)”)—no successful `df.to_csv(out_path, ...)` to the exact required path followed by `Path.exists()/stat().st_size` and round-trip reload assertions.
- proposed_change: Strengthen the termination policy at anchor `step-4-persist-deliverable-post-save-verification` so it is executed immediately before end_turn as a literal checklist: echo resolved output path; write to that exact path; assert exists+non-empty; reload and assert column order match; only then terminate. Consider adding an explicit “output inventory” check (list workspace files) as the final pre-termination step.

## WORKFLOW-THEMES

- (none this iteration)
