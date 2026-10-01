### [shock-analysis-supply] iteration budget wasted early; no workbook open/edit/save before max_iterations
- signal: failure
- pattern: iteration-budget-progress-guardrail
- anchor: workflow-finish-within-the-iteration-budget
- gap: Despite explicit L2 rules (“Start by opening the workbook”, “measurable progress”, “Pivot rule”, and “Hard guardrail (no silent exit)”), the executor made ~59 tool calls without switching to direct editing of `test-supply.xlsx`, resulting in `stop_reason: max_iterations` / `MaxIterationsReached` and no measurable spreadsheet progress (no evidence of open/edit/save or any seed formula/link).
- proposed_change: Strengthen the L2 section `Workflow: finish within the iteration budget` with a concrete micro-budget and enforced pivot trigger, e.g. “Within the first 1–2 tool calls: open the workbook. By tool call 5: save a draft with at least one cell/formula/link changed. If not, immediately stop all exploration and perform the open→seed-edit→save step.” Add a single-line self-check the executor must state before continuing: “Have I opened the workbook and saved a draft with at least one required edit?”

## WORKFLOW-THEMES

- (none this iteration)
