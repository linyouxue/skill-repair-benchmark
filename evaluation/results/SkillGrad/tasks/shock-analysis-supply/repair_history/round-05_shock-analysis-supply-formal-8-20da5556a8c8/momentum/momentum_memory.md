# Pattern record (updated)

### iteration-budget-progress-guardrail | workflow | executor stalls until max_iterations instead of switching to a step-bounded plan that produces a final workbook
- anchor: workflow-finish-within-the-iteration-budget
- appeared_in: iter_1, iter_2, iter_3, iter_7
- description: The run fails to produce a completed/verified spreadsheet because it does not enter the concrete xlsx editing workflow early enough, and/or it burns the harness iteration budget in non-productive steps. A repeated signature is termination with `stop_reason: max_iterations` / `MaxIterationsReached`, often with little or no evidence of actual workbook progress (e.g., `n_skill_invocations: 0` or no measurable workbook edits/saves). The core mechanism is missing workflow control: not timeboxing exploration, not forcing an early “working draft” save, and not reserving iterations for recalc/validation and final export.
- latest_executor_action: For any spreadsheet task, immediately invoke the xlsx workflow and force “measurable progress” within a small fixed number of actions: open the target .xlsx → inspect required sheets/ranges → start writing cells/formulas in small batches → save a working draft → recalc/verify with LibreOffice → fix errors → final save → stop. Enforce the micro-budget: open within 1–2 tool calls; by ~5 tool calls save a draft with at least one required edit. If you miss the micro-budget (no measurable progress), abort exploration and pivot to direct workbook editing immediately. Reserve the final portion of the iteration budget for recalc/verification and final save; do not stop/`end_turn` before at least one required edit has been made and saved.
- remedy_log:
  - iter_1 | diagnosis: run terminated with stop_reason max_iterations; no final message; n_skill_invocations: 0
            | patch: record need for step-bounded plan + early skill invocation guardrail; no current xlsx SKILL anchor for harness-level budget control
  - iter_2 | diagnosis: agent ended immediately (“end_turn”) with zero spreadsheet actions; did not open/modify workbook or populate any required sheets
            | patch: map this failure to existing xlsx L2 section “Workflow: finish within the iteration budget”; tighten anchor and reinforce pivot-to-edit requirement
  - iter_3 | diagnosis: iteration budget wasted early; repeated tool calls without switching to direct `test-supply.xlsx` editing; terminated by MaxIterationsReached with no measurable spreadsheet progress
            | patch: extend pattern evidence to include repeated-iteration stall despite explicit “Start by opening the workbook” and “Pivot rule”; no new anchor yet (rule already exists in L2)
  - iter_7 | diagnosis: run again terminated with `MaxIterationsReached` before producing a completed/verifiable spreadsheet; diagnosis notes `n_skill_invocations = 0` and absence of timeboxing/checkpointing
            | patch: no skill content change in this step (PatternRecordWriter); reinforce that the existing L2 budget guardrail is the correct anchor but is not being followed in execution
