# 论文匿名化训练结果

SkillHone 使用 GPT-5.2 在原题第五轮提交了三篇匿名 PDF。旧 verifier 的 reward 为 0。用本任务的逐项 verifier 复算为 **59/67（88.06%）**，身份字段 14/20、标题和正文保留 42/44、元数据 3/3。原运行记录的显式 Skill 调用数为 0。

[第五轮冻结 Skill](skillhone-gpt5.2/skills/) · [当轮提交和复算明细](skillhone-gpt5.2/evidence/train/run_01/) · [旧评分及执行记录](https://github.com/linyouxue/skill-repair-benchmark/tree/745816c178cb1bb5c0f0e9900baaf9b698b36c49/evaluation/results/SkillHone-GPT52-31Tasks-20261119/tasks/paper-anonymizer/repaired_run) · [四组泛化评测状态](../evaluation/results/README.md)

用于泛化评测的是复审后选定的第 3 轮。[选版依据](skillhone-gpt5.2-round3/selection.json) · [第 3 轮完整 Skill](skillhone-gpt5.2-round3/skills/) · [五组逐次运行索引](../evaluation/results/runs.json)
