# A 组 2023 年训练失败诊断

这份材料对应 Tatu GPT‑5.2 xhigh 在 A 组 2023 年训练数据上的原 Skill baseline。按运行编号选取首条已有实际输出和完整轨迹的有效失败，逐项正确率为 **24/43（55.81%）**。

| 材料 | 文件 |
|---|---|
| 训练题面与两份冻结输入 | [题面](task_prompt.md)、[储备模板](inputs/test-rar.xlsx)、[月度金价](inputs/gold-prices.xlsx) |
| 原 Skill | [完整 xlsx bundle](../environment/skills/xlsx/) |
| 完整失败轨迹 | [ATIF](records/atif.json)、[ACP](records/acp_trajectory.jsonl)、[LLM](records/llm_trajectory.jsonl) |
| 允许反馈 | [43 项对错](outputs/allowed_feedback.json) |
| 实际交付 | [训练失败工作簿](outputs/rar_result.xlsx) |
| 运行索引 | [index.json](index.json) |

使用原 Skill、训练题面、两份输入、实际失败工作簿、完整轨迹和允许反馈进行诊断、修复与选版。2025 年的两个测试组留在评测侧。此前使用 2025 年训练材料生成的候选不纳入这一划分的修复与选版。
