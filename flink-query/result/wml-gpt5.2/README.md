# WML + GPT-5.2 Flink 结果

本目录按 `flink-query/result` 交付约定保存冻结 Skill、repair 组尝试、环境参考验收和审计证据。

## 状态

| 数据集 | 采用 attempt | 审计状态 | 奖励 | 说明 |
|---|---|---|---:|---|
| `repair` | 无 | 无有效结果 | — | 所有已运行尝试因配置、镜像、API/空闲超时或异常结束而无可采用结果。保留各次 attempt 记录。 |
| `scale` | `wml-flink-scale-04` | 有效失败 | 72.39% | 1,917 / 2,648 项正确，输出含 727 个应排除作业。 |
| `stages` | `wml-flink-stages-07` | 有效失败 | 72.36% | 958 / 1,324 项正确，输出含 362 个应排除作业。 |
| `combined` | `wml-flink-combined-04` | 有效失败 | 95.77% | 2,536 / 2,648 项正确，输出含 108 个应排除作业。 |

三组泛化测试各只有一条审计有效成绩，等权均值为 80.17%。有效结果表示执行与 verifier 证据可复核，不代表任务通过。基础设施无效 attempt 的 0 分不作为模型失败成绩。

## 证据

- `skills/` 保存完整冻结 Skill bundle，SHA-256 清单位于 `skills.sha256`。
- `evidence/repair/` 保存所有 repair attempt 的记录、评分和可用轨迹。
- `evidence/environment/` 保存四组官方参考解法通过 verifier 的环境验收证据。
- `attempts.json` 与 `audit-summary.json` 提供逐次状态、重跑关系和审计计数。
- `audit-report.md` 记录环境、verifier、轨迹及产物复核结论。
- `package-manifest.json` 记录原始实验目录和打包输入摘要。

每个 `run.json` 的 `evidence.files` 列出同目录材料。ACP、LLM 和 ATIF 轨迹以 XZ 压缩副本交付，源 attempt 目录未改写。模型生成的 Java/JAR 未由执行器独立导出，因此没有作为可重新编译的交付件；实际输出、Maven/Flink 日志和 verifier 评分均随 attempt 记录保存。
