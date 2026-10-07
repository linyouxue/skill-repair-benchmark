# skillrevise-bundle-gpt52-fail39-published-trace-top3-r4

This package exports 39 published GPT-5.2 Original-Skill FAIL tasks
diagnosed and repaired by the bundle-aware SkillRevise extension.

- `submission.json` contains the task-level diagnoses and final bundle paths.
- Each `tasks/<task-id>/original_run/` is Lin's published representative
  Original-Skill rollout.
- Each `tasks/<task-id>/repaired_skill/` is the exact final bundle selected by
  SkillRevise.
- 33 tasks selected a real method-skill rollout; their matching evidence
  is in `repaired_run/`. The remaining tasks had no accepted edit, so their final
  bundle is intentionally the unchanged Original bundle and no after-run is
  fabricated.
- `provenance.json` records target selection, diagnosis/revision decisions, and
  artifact provenance for every task.

## No-Skill baseline

`baselines/no_skill/no_skill_merged.json` is the final merged no-skill baseline
for the same 39 tasks. Its compact summary is in
`baselines/no_skill/no_skill_merged_summary.json`: all 39 tasks have a valid
score and there are zero infrastructure errors.

Run the official converter from the benchmark checkout:

```bash
python3 evaluation/results/export_trajectory.py --root <this-directory>
```

## Gold-scored versus complete record

`submission.json` contains exactly the 31 tasks in the published SkillsBench-87 Gold and is the input for the official evaluator. `submission_all39.json` preserves all 39 failed-task diagnoses and repair artifacts. The eight remaining tasks are documented in `not_scored_by_gold.json`; they are retained for audit but excluded from Gold scoring.
