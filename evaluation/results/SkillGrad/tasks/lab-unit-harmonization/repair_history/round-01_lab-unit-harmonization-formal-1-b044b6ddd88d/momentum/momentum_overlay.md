### [lab-unit-harmonization] ended without producing `/root/ckd_lab_data_harmonized.csv`
- signal: failure
- pattern: persist-required-deliverables
- anchor: (none)
- gap: The rollout terminated at end_turn without any file-writing action; output inventory is empty, indicating the required harmonized CSV was never created/saved. The skill content covers parsing, conversion, and formatting, but lacks an explicit mandatory “write deliverable + verify existence/format” completion gate.
- proposed_change: Add an L2 section (new anchor suggestion: `persist-and-verify-output`) to SKILL.md: “Before finishing, always write the final dataframe to the exact requested path, then re-open and validate: file exists/non-empty; columns/shape match expectations; no NaNs; all numeric fields are strings formatted as fixed-point with 2 decimals; forbid scientific notation and thousand separators.” Optionally add a short code snippet showing `to_csv(..., index=False)` plus a post-save readback check.

## WORKFLOW-THEMES

- (none this iteration)
