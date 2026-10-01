# Pattern record (updated)

### iteration-budget-progress-guardrail | workflow | executor stalls until max_iterations instead of switching to a step-bounded plan that produces a final workbook
- anchor: workflow-finish-within-the-iteration-budget
- appeared_in: iter_1, iter_2, iter_3
- description: The run fails to produce a completed/verified spreadsheet because it does not enter the concrete xlsx editing workflow early enough, and/or it burns the harness iteration budget in non-productive steps. In iter_1 this manifested as `stop_reason max_iterations` with `n_skill_invocations: 0` (no spreadsheet workflow at all). In iter_2 it manifested as an immediate `end_turn` without any spreadsheet-app actions: no workbook open, no cell writes, no sheet population, no recalc/verification. In iter_3 it again hit `stop_reason: max_iterations` with 59 tool calls and still no measurable spreadsheet progress (no evidence the workbook was opened/edited/saved).
-
- latest_executor_action: For any spreadsheet task, immediately invoke the xlsx workflow and force “measurable progress” within a small fixed number of actions: open the target .xlsx → inspect required sheets/ranges → start writing cells/formulas in small batches → save a working draft → recalc/verify with LibreOffice → fix errors → final save → stop. If after a few tool calls there is still no measurable progress (workbook not opened/edited, no sheets identified/populated), abort exploration and pivot to direct workbook editing (even if only placeholders/links first) so the artifact changes are underway well before the iteration cap. Do not `end_turn`/stop until at least one required edit has been made and saved.
- remedy_log:
  - iter_1 | diagnosis: run terminated with stop_reason max_iterations; no final message; n_skill_invocations: 0
            | patch: record need for step-bounded plan + early skill invocation guardrail; no current xlsx SKILL anchor for harness-level budget control
  - iter_2 | diagnosis: agent ended immediately (“end_turn”) with zero spreadsheet actions; did not open/modify workbook or populate any required sheets
            | patch: map this failure to existing xlsx L2 section “Workflow: finish within the iteration budget”; tighten anchor and reinforce pivot-to-edit requirement
  - iter_3 | diagnosis: iteration budget wasted early; repeated tool calls without switching to direct `test-supply.xlsx` editing; terminated by MaxIterationsReached with no measurable spreadsheet progress
            | patch: extend pattern evidence to include repeated-iteration stall despite explicit “Start by opening the workbook” and “Pivot rule”; no new anchor yet (rule already exists in L2)
