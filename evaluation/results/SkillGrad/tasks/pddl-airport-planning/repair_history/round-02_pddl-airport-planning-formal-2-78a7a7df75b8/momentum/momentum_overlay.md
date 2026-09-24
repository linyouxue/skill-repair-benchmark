### [pddl-airport-planning] ended without producing any required plan_output files
- signal: failure
- pattern: persist-plan-outputs-from-problem-json
- anchor: finalize-persist-required-plan-artifacts
- gap: The run terminated (“end_turn”) after some tool activity but never executed the required manifest-driven loop: `read problem.json → for each (domain, problem, plan_output): solve → write plan_output`. Evidence cited in diagnosis: `n_skill_invocations: 0` and no generated plan artifacts in the output inventory. The missing guardrail is an explicit “don’t terminate until all plan_output paths exist and are non-empty (per harness convention)” check.
- proposed_change: Strengthen L2 `Finalize: persist required plan artifacts` (anchor `finalize-persist-required-plan-artifacts`) into an explicit pre-end checklist: (1) read `problem.json` and enumerate outputs; (2) for each item, write to the exact `plan_output`; (3) read-back verification; (4) end-of-run assertion that all outputs exist (and are non-empty when a plan exists). Also add/strengthen the pointer trigger: “If `problem.json` contains `plan_output`, must follow references/persist_plan_outputs.md; do not `end_turn` before the end-of-run verification passes.”

## WORKFLOW-THEMES

- (none this iteration)
