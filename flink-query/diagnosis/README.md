# repair 原 Skill 失败诊断

这里使用原 Skill baseline 的 `repair` 第 1 条，来自 `flink-v2-repair-original-guard3-r02-checkpoint-01`。GPT-5.2 xhigh 在该次运行的逐作业正确率为 **960/1,324（72.51%）**。

| 材料 | 入口 |
|---|---|
| 修复题、日志和原 Skill | [题面](../task.md)、[冻结日志](../environment/workspace/data/)、[完整原 Skill](../environment/skills/) |
| 实际交付 | [Flink 输出](outputs/actual-flink.txt) |
| 允许反馈 | [阶段和边界汇总](outputs/allowed_feedback.json) |
| 运行记录 | [分数、运行标识和请求计数](../result/baseline/evidence/repair/flink-v2-repair-original-guard3-r02-checkpoint-01/run.json) |

这次运行正确输出了 642 个正例，正确排除了 318 个负例。实际输出包括没有 FINISH 的作业，也包括有 FINISH 但没有 Task SUBMIT 的作业。用 `repair` 输入和反馈定位这类问题，冻结 Skill 后再评估三组泛化。

完整轨迹按运行存放，提供 [ACP](../result/baseline/evidence/repair/flink-v2-repair-original-guard3-r02-checkpoint-01/trajectory/acp_trajectory.jsonl.xz)、[LLM 请求响应](../result/baseline/evidence/repair/flink-v2-repair-original-guard3-r02-checkpoint-01/trajectory/llm_trajectory.jsonl.xz) 和 [ATIF](../result/baseline/evidence/repair/flink-v2-repair-original-guard3-r02-checkpoint-01/trainer/atif.json.xz)。原会话首段保存在同一运行目录的 `continuation-source/`。XZ 文件可用 Python 的 `lzma` 模块或 `xz -dk` 解压。
