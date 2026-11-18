# 结果交付

这里提供修复组的运行记录和实际使用的冻结 Skill。三组泛化成绩按同一运行标识查阅。

| 方法 | Skill 与修复组证据 | 三组测试 |
|---|---|---|
| 原 Skill Baseline | [原 Skill](../environment/skills/) · [修复组记录](baseline/evidence/repair/) | [测试记录](../evaluation/results/baseline/) |
| SkillHone | [冻结 Skill](skillhone-gpt5.2/skills/) · [开发与修复组记录](skillhone-gpt5.2/evidence/) | [测试及 Maven 补测](../evaluation/results/methods/skillhone-gpt5.2/) |
| 人工修复 | [r1 Skill](manual/skills/r1/) · [r2 Skill](manual/skills/r2/) · [修复组记录](manual/evidence/) | [测试及补测](../evaluation/results/manual/) |

SkillHone 在 `repair` 上执行五轮开发评分，冻结第 3 轮候选。人工修复 r1 是早期试跑，r2 用于四组正式对照。逐次记录中可查看模型请求数、显式 Skill 调用次数和现存的 verifier 汇总。

[完整成绩和运行索引](../evaluation/results/README.md)

每条 `run.json` 所在目录附有执行器原始结果、评分、实际输出，以及 XZ 压缩的 ACP、LLM 和 ATIF 轨迹。`run.json` 的 `evidence` 字段索引这些文件。SkillHone 的五轮原生修复记录位于 `skillhone-gpt5.2/evidence/repair/`。实际 Java 工作区与 JAR 存放在 [工作区归档](https://github.com/linyouxue/skill-repair-benchmark/releases/tag/flink-v2-evidence-20261118)，按原始运行 ID 查找。
