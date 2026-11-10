# 历史失败诊断材料

这份材料对应 GPT‑5.2 在 **SkillsBench 原黄金题**上的失败运行。模型正常生成了 Excel，原 verifier 为 3 项通过、2 项失败，reward 为 0。新的 A 组 2025 训练集使用另一批国家，因此这次历史运行没有按新训练集计算 43 项正确率。

| 材料 | 位置 |
|---|---|
| 原题和原输入 | [task_prompt.md](task_prompt.md)、[原 Excel](inputs/test-rar.xlsx) |
| 原 Skill | [完整 xlsx bundle](../environment/skills/xlsx/) |
| 完整失败轨迹 | [ATIF](records/atif.json)、[ACP 事件](records/acp_trajectory.jsonl)、[LLM 请求和响应](records/llm_trajectory.jsonl) |
| 允许反馈 | [测试对错](outputs/allowed_feedback.json) |
| 原产物归档 | [实际 Excel](outputs/rar_result.xlsx)，供组织者复核 |
| 运行索引 | [index.json](index.json) |

原 Skill 以 AgentContext 全文预载，显式 Skill 工具调用数为 0。失败轨迹、原题、原 Skill 和允许反馈直接交给现有 adapter。历史产物含较早的公开金价，覆盖 2023 测试窗口，原 Excel 只留作审计，放在修复和选版输入之外。训练侧使用 A 组 2025 输入，测试输入、参考值和评分由评测侧隔离。
