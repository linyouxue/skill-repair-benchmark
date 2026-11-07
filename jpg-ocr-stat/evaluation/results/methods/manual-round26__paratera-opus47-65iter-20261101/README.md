# 人工 Round26：group1 / group3 泛化评测

| 组别 | 记录 r01 | 记录 r02 | 记录 r03 | 均值 |
|---|---:|---:|---:|---:|
| group_01 | 75.00% | 92.50% | 95.00% | **87.50%** |
| group_03 | 90.00% | 87.50% | 87.50% | **88.33%** |

每组汇总3份运行记录，每份记录对应20张小票、40个日期/金额字段。均值为三份记录字段正确率的算术均值；六份记录合计211/240，字段正确率87.92%。`r01`、`r02`、`r03` 为本次发布的记录编号（`record_id`），各目录 `run.json` 与 `runs.csv` 统一使用该编号。逐次指标见[runs.csv](runs.csv)，汇总与运行编号见[summary.json](summary.json)。

执行模型为 `paratera/Claude-Opus-4.7`，使用统一 BenchmarkExecutor / OpenHands；每次最多65次父迭代，completion guard最多续接1次并共用65次额度，输出上限16384 tokens。各份记录对应的运行ID、实际轮数和终止原因保存在 `run.json`。`n_skill_invocations=0`；5份完整Skill正文已通过上下文预载提供，实际首个请求的正文与冻结版本核对一致。

- 冻结Skill：[manual-round26__paratera-opus47-65iter-20261101/skills](https://github.com/linyouxue/skill-repair-benchmark/tree/e2ac4cbded70cdb51d089036a869d923cf18cef3/jpg-ocr-stat/result/manual-round26__paratera-opus47-65iter-20261101/skills)，包含支持文件与许可；修复过程沿用该结果目录。
- 数据版本：[evaluation@f62fe73e](https://github.com/linyouxue/skill-repair-benchmark/tree/f62fe73e2c1dee38dc092047454dda71ffaa3782/jpg-ocr-stat/evaluation)，使用当前group1/3图片。
- 原始Excel、评分、执行配置、用量和轨迹按组分别放在 `group_01/run_01` 至 `run_03`、`group_03/run_01` 至 `run_03`。Excel与verifier前归档中的原文件逐字节一致；ACP、LLM记录采用无损压缩并核对解压一致性。
- `group_03/run_03` 保留原生65轮会话与恢复记录，HTTP日志捕获45次请求响应；具体覆盖情况见该次 `trajectory/archive-receipt.json`。

| 组别 | 记录编号 | 字段正确数 | 原Excel | 原评分 | 轨迹 |
|---|---|---:|---|---|---|
| group_01 | r01 | 30/40 | [Excel](group_01/run_01/stat_ocr.xlsx) | [评分](group_01/run_01/verifier/accuracy.json) | [LLM](group_01/run_01/trajectory/llm_trajectory.jsonl.xz) · [ACP](group_01/run_01/trajectory/acp_trajectory.jsonl.gz) |
| group_01 | r02 | 37/40 | [Excel](group_01/run_02/stat_ocr.xlsx) | [评分](group_01/run_02/verifier/accuracy.json) | [LLM](group_01/run_02/trajectory/llm_trajectory.jsonl.xz) · [ACP](group_01/run_02/trajectory/acp_trajectory.jsonl.gz) |
| group_01 | r03 | 38/40 | [Excel](group_01/run_03/stat_ocr.xlsx) | [评分](group_01/run_03/verifier/accuracy.json) | [LLM](group_01/run_03/trajectory/llm_trajectory.jsonl.xz) · [ACP](group_01/run_03/trajectory/acp_trajectory.jsonl.gz) |
| group_03 | r01 | 36/40 | [Excel](group_03/run_01/stat_ocr.xlsx) | [评分](group_03/run_01/verifier/accuracy.json) | [LLM](group_03/run_01/trajectory/llm_trajectory.jsonl.xz) · [ACP](group_03/run_01/trajectory/acp_trajectory.jsonl.gz) |
| group_03 | r02 | 35/40 | [Excel](group_03/run_02/stat_ocr.xlsx) | [评分](group_03/run_02/verifier/accuracy.json) | [LLM](group_03/run_02/trajectory/llm_trajectory.jsonl.xz) · [ACP](group_03/run_02/trajectory/acp_trajectory.jsonl.gz) |
| group_03 | r03 | 35/40 | [Excel](group_03/run_03/stat_ocr.xlsx) | [评分](group_03/run_03/verifier/accuracy.json) | [LLM](group_03/run_03/trajectory/llm_trajectory.jsonl.xz) · [ACP](group_03/run_03/trajectory/acp_trajectory.jsonl.gz) |
