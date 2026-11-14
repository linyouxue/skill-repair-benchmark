# 黄金储备风险评测结果

本轮以 A 组 2023 年为训练集。下表为各次 43 项正确数，括号为组内算术均值。所有执行使用 Tatu GPT-5.2 xhigh、OpenHands 和每个 Step 最多 60 次父迭代。Skill 正文通过 AgentContext 预载，35 条运行的显式 Skill 工具调用数均为 0。

| 数据集 | 原 Skill Baseline | SkillHone | 人工修复 |
|---|---:|---:|---:|
| `train` · A 组 2023 | 24/43、23/43、0/43（36.43%） | 23/43、27/43（58.14%） | 43/43、43/43、43/43（100.00%） |
| `group_01` · B 组 2023 | 23/43、23/43、16/43（48.06%） | 23/43、43/43、24/43（69.77%） | 43/43、43/43、43/43（100.00%） |
| `group_02` · A 组 2025 | 16/43、23/43、23/43（48.06%） | 16/43、16/43、23/43（42.64%） | 43/43、43/43、43/43（100.00%） |
| `group_03` · B 组 2025 | 23/43、23/43、16/43（48.06%） | 43/43、23/43、9/43（58.14%） | 43/43、43/43、43/43（100.00%） |
| 三组测试均值 | **48.06%** | **56.85%** | **100.00%** |

- [原 Skill Baseline](baseline/) 有三组各三次正式测试。训练证据与原 Skill 入口见[训练 Baseline](../../result/baseline/README.md)。旧划分的 `group_02`、`group_03`、`train`、`group_01` 依次映射到当前 `train`、`group_01`、`group_02`、`group_03`。原 rollout ID 保留。A 组 2025 年三次采用已有离线复评分，运行目录同时保留原评分。
- [SkillHone 测试](methods/skillhone-gpt5.2/README.md)有三组各三次正式测试。[冻结 Skill、修复记录和两次训练](../../result/skillhone-gpt5.2/README.md)。
- [人工修复测试](manual/README.md)有三组各三次正式测试。[冻结 Skill、修复说明和三次训练](../../result/manual/README.md)。

[逐次索引 CSV](runs.csv)记录 split、rollout ID 与证据路径，[汇总 JSON](summary.json)记录逐次正确数和均值。每次保留实际输出 Excel、评分、执行器记录、ACP、ATIF 与完整 LLM 请求响应。LLM 使用无损 XZ 压缩。
