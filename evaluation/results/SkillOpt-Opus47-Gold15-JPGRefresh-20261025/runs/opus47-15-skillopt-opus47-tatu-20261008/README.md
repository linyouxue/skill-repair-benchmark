# Opus 4.7 baseline → SkillOpt with Opus 4.7

- Baseline: the requested 15 failed original-skill trajectories selected from `Opus47-OriginalSkill-79Tasks-20260920`.
- Task source: local snapshots copied from the upstream SkillsBench task packages.
- Method: SkillOpt only; diagnosis is its built-in diagnosis stage.
- Optimizer and same-task gate model: Tatu `claude-opus-4-7`.
- Parameters: diagnosis samples `N=3`, edit budget `L=4`, progressive repair rounds `R=2`.
- Parallelism: three workers; diagnosis samples within each task remain sequential.
- Outputs: `methods/skillopt`, `jobs`, and `logs` stay inside this run directory.
- The current exported Gold15 submission, with the refreshed `jpg-ocr-stat` result, lives outside this run under `../submissions-skillopt-20261025/opus47-gold15-jpg-refresh`.

The same-task gate is used for keep/revert and is not a held-out validation set.
