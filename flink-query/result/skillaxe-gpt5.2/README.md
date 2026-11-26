# SkillAxe GPT-5.2 Flink generalization

The SkillAxe adapter used the official repair split diagnosis materials. It changed only `senior-data-engineer/SKILL.md`. The three holdout runs used the same [frozen Skill bundle](skills/). Model calls used GPT-5.2 via TatuCloud.

| Split | Reward | Run evidence |
| --- | ---: | --- |
| scale | 0.95619 | [Run record](evidence/scale/skillaxe-flink-group1-infra-07/run.json) |
| stages | 0.95770 | [Run record](evidence/stages/skillaxe-flink-group2/run.json) |
| combined | 0.00000 | [Run record](evidence/combined/skillaxe-flink-group3/run.json) |

Unweighted mean reward is 0.63797. All three runs completed with verifier scores. Credential-like strings in the published evidence are replaced with redaction markers. The combined run received zero because the task output was empty.

[Repair generation and provenance](evidence/repair/) · [Machine-readable summary](evidence/summary.json)
