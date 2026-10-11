# Dual SkillOpt submission workspace

The two tracks have different task sets and benchmark versions, so they remain evaluator-compatible as two separate submissions:

- `outputs/gpt52-31/submission.json`: 31-task GPT-5.2-baseline experiment.
- `outputs/opus47-15/submission.json`: 15-task Opus-4.7-baseline experiment.

Generate the two payloads, their per-task health sidecars, and the top-level
combined index with:

```bash
/Users/elsie/Desktop/SkillOpt-eva/skill-repair-benchmark/.venv/bin/python \
  /Users/elsie/Desktop/SkillOpt-eva/scripts/export_dual_submissions.py \
  --include-unhealthy
```

The top-level `submission.json` summarizes the two tracks but is not directly passed to the single-version evaluator.

Current exported snapshot:

- GPT-5.2 baseline track: 31 tasks exported; 27 healthy and 4 unhealthy.
- Opus-4.7 baseline track: 15 tasks exported; all 15 healthy.
- `outputs/<track>/submission.json` is evaluator-compatible and contains every
  configured task.
- `outputs/<track>/run_status.json` is a non-evaluator sidecar recording strict
  health, comparability, pass/fail, bundle provenance, and validation issues.

For an unhealthy task with a retained `best_skill`, that bundle is exported
without claiming the run was healthy. If no final candidate bundle survived
cleanup, the complete original Skill bundle is exported as a fail-closed
fallback and identified as `original_skill_fallback` in `run_status.json`.

The evaluator submission is intentionally only the final scoring payload. For
the raw optimization evidence, candidate-to-execution mapping, data split
declaration, commands, configuration, and records that were not enabled or
were not retained, see [`EXPERIMENT_RECORDS.md`](EXPERIMENT_RECORDS.md) and
package the two complete run directories together with this directory.
