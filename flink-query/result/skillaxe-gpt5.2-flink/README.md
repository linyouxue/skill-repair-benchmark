# SkillAxe GPT-5.2 Flink generalization

The SkillAxe adapter used the official repair split diagnosis materials. It changed only `senior-data-engineer/SKILL.md`. The three holdout runs used the same [frozen Skill bundle](skills/). Model calls used GPT-5.2 via TatuCloud.

| Split | Reward | GPT-5.2 deployment | Run evidence |
| --- | ---: | --- | --- |
| scale | 0.95619 | AZUREOPENAI-default | [Run record](evidence/scale/skillaxe-flink-group1-infra-07/run.json) |
| stages | 0.95770 | AZUREOPENAI-default | [Run record](evidence/stages/skillaxe-flink-group2/run.json) |
| combined | 0.95770 | AIHUBMIX-default | [Run record](evidence/combined/skillaxe-flink-group3-audit-r06/run.json) |

The descriptive mean across the three recorded scores is 0.95720. It combines two deployments. All three adopted runs are valid failures under the verifier.

The original [combined attempt](evidence/combined/skillaxe-flink-group3/run.json) scored 0 because its output was empty. The adopted AIHUBMIX rerun produced 1,396 parseable rows and scored 2,536/2,648. Credential-like strings in the published traces are redacted.

[Combined attempt history](evidence/combined/README.md) · [Repair generation and provenance](evidence/repair/) · [Machine-readable summary](evidence/summary.json)
