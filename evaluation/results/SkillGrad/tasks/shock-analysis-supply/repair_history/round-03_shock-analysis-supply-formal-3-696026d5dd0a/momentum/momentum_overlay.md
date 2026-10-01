### [shock-analysis-supply] did not edit workbook; never entered spreadsheet workflow
- signal: failure
- pattern: iteration-budget-progress-guardrail
- anchor: workflow-finish-within-the-iteration-budget
- gap: The trajectory contains zero spreadsheet-app actions (no workbook open, no cell writes, no solver/recalc) and terminates via `end_turn`. This violates the L2 requirements to “Enter the spreadsheet workflow immediately” and apply the “Pivot rule” after a small number of non-progress tool calls; the executor never pivoted into direct workbook editing at all.
- proposed_change: Strengthen the L2 “Workflow: finish within the iteration budget” section to include a hard guardrail: if the task provides an .xlsx path, the first concrete step must be opening the workbook and listing required sheets; disallow `end_turn` until at least one measurable progress condition is met (opened workbook and wrote at least one required formula/link). Add an explicit checklist in that section: open → identify sheets → write 5–10 seed formulas/links → save → recalc.py → fix errors → proceed.

## WORKFLOW-THEMES

- (none this iteration)
