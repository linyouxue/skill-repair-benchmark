# SkillAxe / Claude 4.7 / group_01 and group_03

- Skill 版本：沿用 `jpg-ocr-stat/result/skillaxe-claude4.7/skills/` 的冻结版本；5-Skill bundle SHA-256 为 `e39e41fca5d0044d7b5dd4eb05551759871d187c5f85aa6b437f8bc097323aa8`，未根据泛化成绩修改或重新选择。
- 数据：`group_01`、`group_03` 各 20 张小票，每次固定 40 个日期/金额字段；这是用户明确要求追加的泛化运行，与仓库原先只要求 group2 的安排分开披露。
- 执行配置：`paratera/Claude-Opus-4.7`、BenchFlow `v0.6.7` / commit `aadad44acf27f193df98f438443116d514f51fb8`、OpenHands CLI commit `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`；每次最多 65 次 parent iteration。
- 六次有效运行均保留原生 `result.json`、`benchmark_result.json`、配置、ACP 轨迹、完整 LLM 轨迹的无损 XZ、trainer、用量/时间和 verifier 原始输出。`GROUP13_AUDIT.json` 记录原始日志与 XZ 的大小及 SHA-256。
- 证据限制：这六次有效运行的执行器没有把运行时 `/app/workspace/stat_ocr.xlsx` 导出到 rollout 的 `artifacts/`；verifier 已成功完成字段评分，但原 Excel 在容器销毁后无法恢复。各 run 的 `artifacts/MISSING_STAT_OCR.md` 明确记录该缺口；没有从预测、日志、baseline 或 oracle 伪造 Excel。
- 基础设施失败尝试不计入以下均值。本提交只包含六次既定有效运行，没有按成绩挑分重跑。

| 组别 | 第1次 | 第2次 | 第3次 | 均值 |
|---|---:|---:|---:|---:|
| group_01 | 65.00%（26/40） | 55.00%（22/40） | 62.50%（25/40） | **60.83%（73/120）** |
| group_03 | 80.00%（32/40） | 85.00%（34/40） | 85.00%（34/40） | **83.33%（100/120）** |

| 运行目录 | 原生 run ID | 已用父步/65 | 终止原因 | Excel |
|---|---|---:|---|---|
| `group_01/run_01` | `group01_run_01-attempt-01` | 65/65 | `max_iterations` | 未归档 |
| `group_01/run_02` | `group01_run_02-attempt-01` | 65/65 | `max_iterations` | 未归档 |
| `group_01/run_03` | `group01_run_03-attempt-07` | 56/65 | `end_turn` | 未归档 |
| `group_03/run_01` | `group03_run_01-attempt-01` | 65/65 | `max_iterations` | 未归档 |
| `group_03/run_02` | `group03_run_02-attempt-02` | 65/65 | `max_iterations` | 未归档 |
| `group_03/run_03` | `group03_run_03-attempt-01` | 63/65 | `end_turn` | 未归档 |

