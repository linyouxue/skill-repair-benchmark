### [pddl-airport-planning] Missing required output artifacts (no plan files at plan_output paths)
- signal: failure
- pattern: persist-plan-outputs-from-problem-json
- anchor: finalize-persist-required-plan-artifacts
- gap: The run reached end_turn without performing the mandated completion gate in **"Finalize: persist required plan artifacts"**: it did not re-open problem.json to re-enumerate every required plan_output, did not write exactly one plan file to each plan_output path, did not read-back verify each file, and did not assert that all required plan_output paths exist on disk. The observed outcome (execution_ok: true, no plan validity/quality error reported) matches the missing-artifacts failure mode.
- proposed_change: Strengthen the L2 Finalize section into a non-skippable end-of-run checklist requiring an explicit, logged "persist_all(manifest_path)" step (pointer to references/persist_plan_outputs.md) immediately before end_turn, and require the executor to enumerate the plan_output list in the final message (or log) to prove the re-open/re-enumerate happened. If this still recurs, add a hard rule: "Never call end_turn until a file-system existence check over all plan_output paths passes".

## WORKFLOW-THEMES

- (none this iteration)
