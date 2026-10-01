### [shock-analysis-supply] iteration-limit stall prevents any completed/verified spreadsheet output
- signal: failure
- pattern: iteration-budget-progress-guardrail | new
- anchor: (none)
- gap: The trajectory hits `max_iterations` without producing a final agent message or completed workbook. Evidence indicates `n_skill_invocations: 0`, so the executor never entered the xlsx skill workflow (open/edit/recalc/verify/save) and instead consumed the entire tool budget without measurable artifact progress.
- proposed_change: Add a workflow guardrail outside (or at the top of) the xlsx skill: require early xlsx-skill invocation and a step-bounded plan (open workbook → enumerate required edits → batch edits → recalc/verify → save/export → stop). Include a pivot rule: if no workbook has been opened/edited after N tool calls, immediately switch to direct workbook editing rather than continuing exploratory loops.

## WORKFLOW-THEMES

- (none this iteration)
