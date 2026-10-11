# SkillOpt complete experiment handoff

本目录是可独立上传的 SkillOpt 实验材料包，整理日期为 2026-10-11。它同时包含：

1. GPT-5.2 baseline 上的 31-task SkillOpt 修复实验；
2. Opus-4.7 baseline 上的 15-task SkillOpt 修复实验；
3. 全部当前保留的 baseline、优化轮次、候选 Skill、候选执行、验证结果、选择记录与终端日志；
4. 两个 benchmark version 各自可被 evaluator 读取的标准 submission；
5. 适配代码、执行器代码快照、运行命令、配置、来源和缺失项声明。

## 当前数据规模

- 2 条彼此隔离的实验 track；
- 46 个任务；
- 42 个严格健康完成，4 个不健康完成；
- 85 个优化轮次；
- 85 个候选 rollout，以及与之逐一对应的 85 个候选 Skill 包；
- 187 份逐 Skill rewrite 原始记录；
- 162 份独立 diagnosis sample，覆盖 54 个轮次；
- 61 次 `revert`，24 次 `keep`；
- 4 个 non-comparable gate round。

四个不健康任务都来自 GPT track：`bike-rebalance`、`fix-build-agentops`、
`simpo-code-reproduction`、`fix-build-google-auto`。它们没有被伪装成有效得分，详细问题见
`submissions/outputs/gpt52-31/run_status.json`。

## 首选入口

- `metadata/TASK_ROUND_INDEX.json`：完整的 task → round → proposal → candidate bundle → rollout → verifier → decision 映射。
- `metadata/TASK_ROUND_INDEX.csv`：适合表格分析的轮次索引。
- `metadata/ARTIFACT_COVERAGE.json`：数量汇总。
- `submissions/submission.json`：两条 submission 的总索引，不能直接作为单一 benchmark 的 evaluator 输入。
- `submissions/outputs/gpt52-31/submission.json`：GPT 31-task 标准 submission。
- `submissions/outputs/opus47-15/submission.json`：Opus 15-task 标准 submission。
- `ARTIFACT_MAP.md`：每类分析材料的位置和语义。
- `DATA_SPLIT_AND_SELECTION.md`：训练、验证、测试及跨轮选择的实际设置。
- `MISSING_OR_NOT_ENABLED.md`：未保存、未启用或已按要求删除的内容。
- `REPRODUCIBILITY.md`：模型、参数、命令、环境和复现边界。
- `metadata/FILE_MANIFEST.sha256`：包内文件逐文件 SHA-256。

## 目录结构

```text
skillopt-analysis-upload-20261011/
├── runs/
│   ├── gpt52-31-skillopt-gpt52-ai360-20261011/
│   └── opus47-15-skillopt-opus47-tatu-20261008/
├── submissions/
├── code/
│   ├── SkillOpt/
│   ├── adapters/
│   ├── scripts/
│   ├── configs/
│   ├── skill-repair-benchmark/
│   └── evaluation/
└── metadata/
```

每个 run 目录中的 `baseline/`、`source_tasks/`、`methods/skillopt/`、`jobs/`、
`shared/`、`commands/` 和 `logs/` 均保留。`.env`、API key、缓存和 Python
字节码没有打包。

## 关于“优化器实际收到的轨迹”

适配器并未把完整 `llm_trajectory.jsonl` 原样放进优化器请求。每轮实际输入的是：

- baseline 的 `benchmark_result.json`；
- 前序失败 gate 的 `gate_result.json`；
- 从这些结果抽取的失败字段、stdout/stderr、trace 等压缩证据；
- 当前 Skill bundle、task context、历史 rejected buffer。

这些输入来源及跨轮累计关系记录在每轮 `evidence_bundle.json` 和任务级
`repair_loop.json`。完整 rollout 轨迹仍保存在 `jobs/.../trajectory/`，供事后分析，
但不应声称它们全部逐字进入过优化器上下文。

## 完整性边界

“完整”指当前实验在执行时实际保留的全部材料。此前按实验要求删除的不健康临时目录
无法从本包恢复；对应错误仍可在 `logs/terminal-*.log` 中审计。31 个早期轮次没有独立
`sample_*.json`，只保留合并诊断、`diagnosis_raw.json` 和最终 rewrite 记录。详情见
`MISSING_OR_NOT_ENABLED.md`。

