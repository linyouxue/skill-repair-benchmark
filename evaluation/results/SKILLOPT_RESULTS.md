# SkillOpt experiment index

SkillOpt results are separated by the model that produced the original
trajectory and by experiment version:

- GPT-5.2, 31 tasks: [`SkillOpt-GPT52-31-EvidenceFix-20261018/`](./SkillOpt-GPT52-31-EvidenceFix-20261018/)
- Opus-4.7, Gold15 with the refreshed JPG experiment: [`SkillOpt-Opus47-Gold15-JPGRefresh-20261025/`](./SkillOpt-Opus47-Gold15-JPGRefresh-20261025/)

The source baselines remain separate:

- GPT-5.2 representative trajectories: [`GPT52-AllTasks-RepresentativeRuns-20260916/`](./GPT52-AllTasks-RepresentativeRuns-20260916/)
- Opus-4.7 original-skill trajectories: [`Opus47-OriginalSkill-79Tasks-20260920/`](./Opus47-OriginalSkill-79Tasks-20260920/)
- Official-skill Core22 baseline: [`OfficialSkillBaseline-Core22-20260916/`](./OfficialSkillBaseline-Core22-20260916/)

For each SkillOpt experiment, start with `README.md`, then read
`submission/summary.md`, `submission/run_status.json`, and
`submission/evidence_index.json`. Raw diagnosis, candidate, rollout, verifier,
and selection records are under that experiment's `runs/` directory.
