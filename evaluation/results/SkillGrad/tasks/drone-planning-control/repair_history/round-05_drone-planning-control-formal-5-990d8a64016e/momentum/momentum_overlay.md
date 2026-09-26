### [drone-planning-control] Missing required per-command results tree and artifacts under `/root/results/<id>/...`
- signal: failure
- pattern: deliverables-loop-nonoptional
- anchor: required-deliverables-loop-non-optional
- gap: The attempt ended without executing the non-optional deliverables loop (enumerate all command IDs → per command: parse → plan → simulate → metrics → save `.npy/.json` → plots → final completeness check). The evaluator failed because no populated `/root/results/<id>/...` tree was produced, even though the run was otherwise “execution_ok: true”.
- proposed_change: Strengthen L2 `position-controller-trajectory-planner` section “Workflow: Required deliverables loop (non-optional)” to include an explicit mandatory *final* on-disk completeness/readability check (assert required files exist and can be loaded/parsed) and a hard stop-condition: do not terminate the attempt until the check passes for every command ID. Point more aggressively to `references/deliverables_driver.md` as the default runnable skeleton when the harness expects `/root/results/<id>/...`.

## WORKFLOW-THEMES

- (none this iteration)
