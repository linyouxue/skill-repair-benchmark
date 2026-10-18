# SkillOpt GPT-5.2 31-task evidence-fix experiment

This directory is the current GPT-5.2 SkillOpt result set. It replaces the
obsolete `SkillOpt-Complete-Experiment-Handoff-20261012` upload. Files are
stored directly in Git; there is no compressed archive or reassembly step.

## Start here

1. `submission/summary.md` — headline result counts.
2. `submission/summary.csv` — one selected result for every task.
3. `submission/run_status.json` — health, pass/fail, repair rounds, decisions,
   model provenance, and source run.
4. `submission/evidence_index.json` — task-by-task links to the raw diagnosis,
   candidate Skill packages, gate attempts, trajectories, verifier output, and
   worker logs.
5. `submission/submission.json` — evaluator-facing standardized submission.

## Result

- 31/31 tasks have healthy and comparable selected results.
- 10 tasks passed and 21 tasks failed.
- 5 infrastructure-invalid gate attempts are preserved for audit and excluded
  from scoring.
- All 55 scored candidate gate executions used `ai360/openai/gpt-5.2`.
- Ten tasks reverted all candidates; their selected final result is therefore
  the imported original GPT-5.2 baseline and retains the historical
  `openrouter/openai/gpt-5.2` provenance. This is expected selection provenance,
  not a gate-model substitution.
- Selection used the same-task keep/revert gate. There was no independent
  validation set and no independent final-test set.

## Raw runs

- `runs/gpt52-31-skillopt-evidencefix-v2-20261017/`: main three-worker run.
- `runs/gpt52-4task-unhealthy-rerun-evidencefix-v3-20261018/`: isolated reruns
  for Exoplanet, Bike, Excel, and the first SimPO architecture diagnosis.
- `runs/gpt52-1task-simpo-amd64-rerun-evidencefix-v4-20261018/`: SimPO AMD64
  rerun, including the preserved ACP hang and the healthy scored retry.

Within each run, `methods/skillopt/<task>/workspace/` contains diagnosis inputs
and full replies, per-round candidate Skills, raw rewrite records, gate attempt
records, gate results, and keep/revert decisions. `jobs/skillopt/` contains the
full executor trajectories and verifier artifacts. `logs/` contains auxiliary
worker terminal logs. `code/` and `commands/` freeze the implementation and
commands used by that run.

Imported baseline job copies and the main run's unmodified task-source snapshot
are intentionally not duplicated here. They are already public at the paths in
`PUBLIC_SOURCES.md`. Patched source snapshots used by the v3/v4 reruns are
included in those run directories.

`metadata/SECURITY_SCAN.json` records the credential scan, and
`metadata/FILE_MANIFEST.sha256` provides file checksums.
