### persist-plan-outputs-from-problem-json | workflow | always write a non-empty plan file to each plan_output path before finishing
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor completes (or times out) without creating any plan output artifacts, leaving the output inventory empty and giving the verifier nothing to check. This is a workflow finalization failure: for SkillsBench PDDL tasks the required deliverable is one plan file per entry in problem.json, written exactly to the provided plan_output paths. Even when planning fails (no plan exists), the run must still write an explicit artifact (e.g., an empty plan file or a file containing a clear failure marker if the harness allows) rather than producing zero files.
- latest_executor_action: At the start, read problem.json and enumerate every required plan_output path. For each problem instance: load domain+problem, generate a plan (or detect unsolvability), then create parent directories and write the plan to the exact plan_output path (one action per line, correct naming). Immediately re-open the written file and confirm it exists and is non-empty (or matches the required empty-plan convention) before moving to the next item. Before exiting, list all plan_output paths and verify they all exist on disk.
- remedy_log:
  - iter_0 | diagnosis: run produced no plan files at all; agent never wrote any generated plan to the required plan_output paths from problem.json
            | patch: (none yet; record initialized from diagnosis)
