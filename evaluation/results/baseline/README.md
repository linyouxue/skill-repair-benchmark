# PDDL / Flink：官方原Skill baseline

24/24有效，2026-10-30完成验收；2026-10-31按evaluation/results/README.md上传。
这是original-skill baseline，没有诊断、Skill修复、候选选择或修复增益。

| 任务 | 输入 | r01 | r02 | r03 | 平均reward | 全对 |
|---|---|---:|---:|---:|---:|---:|
| pddl-airport-planning | original | 1.000000000 | 1.000000000 | 0.000000000 | 0.666666667 | 2/3 |
| pddl-airport-planning | group_01 | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 | 0/3 |
| pddl-airport-planning | group_02 | 0.000000000 | 1.000000000 | 1.000000000 | 0.666666667 | 2/3 |
| pddl-airport-planning | group_03 | 0.000000000 | 0.500000000 | 0.000000000 | 0.166666667 | 0/3 |
| flink-query | original | 0.740936556 | 0.000000000 | 0.000000000 | 0.246978852 | 0/3 |
| flink-query | group_01 | 0.449541284 | 0.449541284 | 0.000000000 | 0.299694190 | 0/3 |
| flink-query | group_02 | 0.469026549 | 0.469026549 | 0.000000000 | 0.312684366 | 0/3 |
| flink-query | group_03 | 0.500000000 | 0.000000000 | 0.000000000 | 0.166666667 | 0/3 |

PDDL平均 **0.375**，全对 **4/12**；Flink平均 **0.256506018504**，全对 **0/12**。
两种任务reward定义不同，不据此做跨任务能力排名。Flink的6次非零运行正例准确率均为1，但负例过滤未全对；其余6次原生0分照实保留。详见各任务scoring-summary.json。

## 目录与提交口径

```text
baseline/
├── README.md / submission.json / STATUS.csv / summary.csv
├── protocol.json / acceptance.json / evidence-assets.json
├── tasks/<task>/
│   ├── original_skill/       # 完整原bundle、支持文件和许可
│   ├── original_runs/<native-run-id>/
│   │   ├── executor_request.json / result.json / benchmark_result.json
│   │   └── trajectory/acp_trajectory.jsonl
│   ├── canonical-slots.json / scoring-summary.json / artifact-index.json
│   └── runs.csv / summary.json / acceptance.json
└── trajectory_timelines/     # 官方export_trajectory.py生成，不手改索引
```

submission.json是两任务baseline的全部运行索引，不伪造diagnoses、repaired_bundle或after轨迹；不将基线冒充Gold诊断/修复提交。
完整原Skill在本目录冻结，未改任何正文或支持文件。数据和原材料版本固定为[556fd216287be7e58480ed5a6dd935ca3370e639](https://github.com/linyouxue/skill-repair-benchmark/tree/556fd216287be7e58480ed5a6dd935ca3370e639)。
没有人工Skill修订、样本专用规则或按泛化分数选版。只读原题/三组输入进行独立基线执行；每组3次，全部正常FAIL/0分计入。

## 模型、执行与评分

- Tatu GPT-5.2 / xhigh，单请求输出上限16384；每槽位累计60父迭代，completion guard最多1次且共享额度，无子Agent。
- OpenHands CLI `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools `1.28.1`；统一本地BenchmarkExecutor含既有runtime/guard/代理接线改动，不冒称无改动main复现。
- 完整Skill正文预载、原生评分、显式Verifier代理和真实归档均已验收。22条n_skill_invocations=0以实际正文注入证据确认，2条为1；callback是重建记录，不是wire dump。
- PDDL按两份要求计划的有效比例评分；Flink按正确输出正例、正确排除负例及额外错误项评分，不把CTRF比例或正例准确率替代reward。

## 原生证据与下载

每次有效槽位的run ID、原生评分路径和真实产物路径见STATUS.csv和tasks/<task>/canonical-slots.json。
原生config/result、ACP、ATIF及官方评分在original_runs中；完整LLM请求/响应、所有保留运行段（含故障段）、slots、usage和实际/app tar见以下无损归档：

- [pddl-airport-planning完整证据](https://github.com/linyouxue/skill-repair-benchmark/releases/download/pddl-flink-gpt52-baseline-20261030/pddl-airport-planning-original-skill-tatu-gpt52-20261030.tar.gz)（199180411字节，602个原文件）
- [flink-query完整证据](https://github.com/linyouxue/skill-repair-benchmark/releases/download/pddl-flink-gpt52-baseline-20261030/flink-query-original-skill-tatu-gpt52-20261030.tar.gz)（1071908589字节，999个原文件）

PDDL真实计划、Flink真实Java/JAR和输出来自各run的artifacts/pre-verifier-workspace.tar.gz，不从文字摘要补造。
原档路径沿用runs/official-tatu-gpt52/及slots/；artifact-index.json将本目录条目与下载归档关联。早期基础设施尝试中原本未归档的文件仍如实缺失，不补造。
生成中断优先原会话/剩余额度恢复；仅Verifier/导出故障使用同次真实产物补验。canonical-slots.json引用有效补验/导出sidecar，原native错误保留，不能用旧raw错误覆盖有效评分。
基础设施故障不计模型0分；旧调用和各恢复段用量保留，不增加24个有效槽位。执行器cost仅为估算，提供商实际扣费未知。

## 轨迹转换

按仓库现有evaluation/results/export_trajectory.py（同一数据提交版本）先--dry-run，再执行实际转换。
original-skill应标为before；不手工改变标签和trajectory_timeline_index.json。
Markdown是官方脚本生成的可读视图，完整原始ACP/LLM另存不截断。仅整理既有实验，新增模型/裁判调用0；不包含正在运行的JPG实验。
