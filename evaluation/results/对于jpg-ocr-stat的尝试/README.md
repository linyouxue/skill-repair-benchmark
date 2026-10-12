# 对于 jpg-ocr-stat 的尝试

本目录保存本地 `jpg-ocr-stat` 人工修复过程中已找到的全部运行记录、各版本 Skill，以及用于分析字段回退的真实产物。不是只挑成功运行的 Gold 集，也不是一次条件完全相同的重复实验。

归档包含人工标注目录中的 70 条尝试，以及早期 SkillAxe 的 4 条尝试（含历史成功 `r004-budget65`）。归档时间、逐条状态及缺失文件以 [MANIFEST.json](MANIFEST.json)、[ATTEMPTS.csv](ATTEMPTS.csv) 为准。最新仍在运行的尝试仅保存有限的轨迹快照，不表示其最终结果；本次上传没有停止、重启或新增实验。

## 从哪里开始看

| 路径 | 内容 |
| --- | --- |
| [ATTEMPTS.csv](ATTEMPTS.csv) | 每条运行的模型、调用上限、评分、终止原因和证据可用性 |
| [MANIFEST.json](MANIFEST.json) | 逐条索引、task digest、条件及实际 Skill 路径 |
| `runs/<rollout_id>/inputs/skills/` | 该次运行冻结的实际输入 Skill bundle；实际加载/正文暴露以轨迹为准，优先以此核对候选版本 |
| `skills/bundles/` | 各 round 和冻结批次中仍存在的完整候选 bundle |
| `skills/round_notes/` | 已有局部补丁、差异及修订说明；不能单独当作完整 Skill |
| `runs/<rollout_id>/trajectory/` | ACP 轨迹及完整 LLM 请求/响应轨迹（脱敏后） |
| `runs/<rollout_id>/agent/acp_trajectory.jsonl` | 原始 Agent 侧 ACP 副本，仅在本地确实存在时保留 |
| `runs/<rollout_id>/results.jsonl.gz` | trainer-facing 结果/轨迹，仅在确实存在时保留 |
| `trajectory_timelines/` | 使用仓库统一导出器生成的可读 Markdown；入口为其中的索引 JSON |
| `runs/<rollout_id>/artifacts/stat_ocr.xlsx` | 实际导出的最终 Excel，不从日志重建 |
| `runs/<rollout_id>/field_evidence/` | 实际保存的字段位置、识别值、状态、检查点及脚本；有些历史运行没有这些证据 |
| `runs/<rollout_id>/verifier/test-status.json` | 官方 verifier 的 summary 与 test name/status 投影，不含隐藏答案或断言正文 |
| `batches/` | 冻结计划及批次状态快照，可用于辨别原 task/修正 task、模型和预算条件 |
| [FILES.json](FILES.json)、[PUBLICATION.json](PUBLICATION.json) | 逐文件来源、压缩/脱敏方式、完整性检查和明确遗漏 |

## 怎么读大轨迹

`llm_trajectory.jsonl.gz` 与 `results.jsonl.gz` 使用标准 gzip。压缩后仍超过 GitHub 单文件限制的轨迹拆为 `llm_trajectory.part-001.jsonl.gz`、`part-002` 等，每卷都是按原顺序排列的完整 JSONL 行；具体文件清单在 `MANIFEST.json` 的 `llm_wire_files` / `trainer_results_files` 中。按编号解压拼接即可恢复整条轨迹。

压缩、分卷没有删除历史上下文、图片载荷或模型响应；JSONL 统一为 UTF-8，每行仍是一条原有记录。仅认证字段和凭据被脱敏。查看单条运行时优先读 Markdown 时间线，需要完整 wire 内容时再解压；不要一次把全部大轨迹加载进内存。

```bash
gzip -dc runs/<rollout_id>/trajectory/llm_trajectory*.jsonl.gz > llm_trajectory.jsonl
gzip -dc runs/<rollout_id>/results*.jsonl.gz > results.jsonl
```

可读时间线不是完整 wire 的替代品：它按仓库统一格式省略 `agent_thought` 正文；完整脱敏记录仍在原生 ACP/LLM 文件中。重复的 before/after 标签按 `condition` 元数据生成，不代表所有运行能一一配对或做因果比较。

## 如何解释状态

- `scored_PASS` / `scored_FAIL`：已有最终结果中 `execution_ok=true` 且 reward 分别为 1 / 0。这里只是忠实投影已有元数据，不代替逐条基础设施健康审计。
- `execution_error_unscored`：执行未正常完成或基础设施中断；不得计入模型 FAIL。
- `completed_unscored`：存在结束记录，但没有有效 reward；不得仅凭诊断字段数填成 PASS/FAIL。
- `incomplete_snapshot`：缺最终结果，包括历史中断留下的记录和归档时仍在运行的那条；不擅自认定失败。

字段审计中的正确数、回退及 checkpoint 都是诊断证据，不等同于正式 reward。检查点是间隔采样，只能证明被观察到的变化，不能声称覆盖每一次中间写盘。缺失的 Excel、LLM 轨迹或最终结果没有被补造；两条早期 SkillAxe 的 Excel 从当时真实的 `pre-verifier-inputs.tar.gz` 中取出，具体来源见 `FILES.json`，没有从日志重建。round 13/18 没有独立候选目录、round 5–12 只有局部补丁，并不表示对应运行不存在：冻结输入仍可在各 run 的 `inputs/skills` 中查看。

## 对照实验的边界

原 task 与修正 task、GPT-5.2 与 Opus 4.7、不同 Skill、60/65/80 次预算及恢复运行不能直接合并算一个成功率。以每条运行的 `executor_request.json`、`config.json`、冻结计划及 `task_digest` 对齐条件。历史 SkillAxe PASS 使用当时的原 task，不能混入修正 task 的重复实验。基础设施恢复产生的无效前次保留在索引中，但不增加有效运行分母。

这里只上传实验数据；没有夹带本地执行器代码改动。没有上传 API key、SSH 私钥、代理认证信息、完整 verifier 源码、隐藏 expected/oracle 文件或原始断言消息。
