### [shock-analysis-supply] iteration budget exhausted (MaxIterationsReached) before any verifiable workbook was produced
- signal: failure
- pattern: iteration-budget-progress-guardrail
- anchor: workflow-finish-within-the-iteration-budget
- gap: Despite an explicit L2 guardrail (“Workflow: finish within the iteration budget”), the run still terminates at `stop_reason: max_iterations` / `MaxIterationsReached` without a completed/verifiable spreadsheet. The diagnosis reports `n_skill_invocations = 0`, implying the executor did not actually enter the xlsx workflow early (open workbook → edit → save draft) and did not reserve iterations for final recalc/verification/export.
- proposed_change: Strengthen the L2 section `Workflow: finish within the iteration budget` to include a mandatory self-audit checklist that must be executed every N tool calls (e.g., after tool call 2 and 5): “Have I opened the workbook? Have I saved a draft with at least one required edit?” If either is no, the next action must be direct `openpyxl load_workbook` + write a seed edit + save. Also add an explicit prohibition: “Do not continue analysis/browsing if `n_skill_invocations` would remain 0 by tool call 2—open the workbook now.”

## WORKFLOW-THEMES

- (none this iteration)
