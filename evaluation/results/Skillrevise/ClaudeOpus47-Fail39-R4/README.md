# skillrevise-bundle-claude-opus47-fail39-published-trace-top3-r4-replay27

This package exports 39 published GPT-5.2 Original-Skill FAIL tasks
diagnosed and repaired by the bundle-aware SkillRevise extension.

- `submission.json` contains the task-level diagnoses and final bundle paths.
- Each `tasks/<task-id>/original_run/` is Lin's published representative
  Original-Skill rollout.
- Each `tasks/<task-id>/repaired_skill/` is the exact final bundle selected by
  SkillRevise.
- 29 tasks selected a real method-skill rollout; their matching evidence
  is in `repaired_run/`. The remaining tasks had no accepted edit, so their final
  bundle is intentionally the unchanged Original bundle and no after-run is
  fabricated.
- `provenance.json` records target selection, diagnosis/revision decisions, and
  artifact provenance for every task.

Run the official converter from the benchmark checkout:

```bash
python3 evaluation/results/export_trajectory.py --root <this-directory>
```
