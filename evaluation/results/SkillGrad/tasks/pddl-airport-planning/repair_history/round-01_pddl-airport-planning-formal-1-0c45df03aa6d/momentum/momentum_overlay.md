### [pddl-airport-planning] missing required plan file artifacts (no outputs written)
- signal: failure
- pattern: persist-plan-outputs-from-problem-json
- anchor: (none yet)
- gap: The run never performed the mandatory persistence/finalization step: it did not read problem.json to enumerate plan_output destinations and did not create/write any plan files. The verifier therefore had nothing to validate.
- proposed_change: Add an L2 workflow rule (e.g., “Finalize: persist artifacts”) that forces: read problem.json → for each entry generate plan → mkdir -p parent dirs → write plan text to exact plan_output path → read-back verification that file exists and is non-empty (or follows the benchmark’s empty-plan convention) → only then terminate.

## WORKFLOW-THEMES

- (none this iteration)
