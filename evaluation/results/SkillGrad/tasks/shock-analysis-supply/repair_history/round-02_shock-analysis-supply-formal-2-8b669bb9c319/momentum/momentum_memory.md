# Pattern record (updated)

### iteration-budget-progress-guardrail | workflow | executor stalls until max_iterations instead of switching to a step-bounded plan that produces a final workbook
- anchor: (none yet)
- appeared_in: iter_1
- description: The run reaches the harness iteration cap (`max_iterations` / `MaxIterationsReached`) without producing a final agent message or a completed/verified spreadsheet. In the iter_1 evidence, this is coupled with `n_skill_invocations: 0`, indicating the executor did not enter the xlsx skill workflow at all; instead it spent the budget in non-productive tool-call loops. This is a control-flow / planning guardrail failure: the executor should detect lack of measurable artifact progress and pivot quickly to a concrete, bounded sequence that results in an output file.
- latest_executor_action: Adopt an iteration-budgeted execution plan for spreadsheet tasks: (1) invoke the xlsx skill immediately to open the workbook/workspace, (2) enumerate required deliverables/sheets/cells, (3) perform edits in batched operations, (4) run formula recalc/verification once, (5) save/export and stop. If after a small fixed number of tool calls there is no concrete artifact progress (no workbook opened/edited, no sheets populated), stop the current loop and switch strategies toward directly producing the required file; do not continue exploratory calls until the cap.
- remedy_log:
  - iter_1 | diagnosis: run terminated with stop_reason max_iterations; no final message; n_skill_invocations: 0
            | patch: record need for step-bounded plan + early skill invocation guardrail; no current xlsx SKILL anchor for harness-level budget control

