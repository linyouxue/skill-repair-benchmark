### [pddl-airport-planning] ended without persisting any required plan_output artifacts from problem.json
- signal: failure
- pattern: persist-plan-outputs-from-problem-json
- anchor: finalize-persist-required-plan-artifacts
- gap: The executor terminated (end_turn) without executing the non-skippable completion gate described in SKILL.md “Finalize: persist required plan artifacts” (re-open problem.json → enumerate all plan_output paths → write one file per path → read-back existence check). The run produced no filesystem outputs at any required plan_output paths.
- proposed_change: Strengthen the L2 “Finalize: persist required plan artifacts” section to require an explicit, named final step (e.g., “run persist_all(manifest_path, solve_one) exactly once as the last action”) plus an explicit pre-end assertion line in the assistant message ("All plan_output files listed in problem.json exist on disk") to make omission more detectable. Consider adding a minimal code snippet in L2 that mirrors references/persist_plan_outputs.md and instructs the executor to literally copy/run it before end_turn.

## WORKFLOW-THEMES

- (none this iteration)
