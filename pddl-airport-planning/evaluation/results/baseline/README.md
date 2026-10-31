# pddl-airport-planning：官方原Skill / Tatu GPT-5.2 baseline

有效 **12/12**，平均reward **0.375000000000**，严格全对 **4/12**。
2026-10-30完成验收；2026-10-31发布到本子数据集的evaluation/results/baseline/。

| 数据集 | 有效次数 | 第1次 | 第2次 | 第3次 | 均值 | 全对次数 |
|---|---:|---:|---:|---:|---:|---:|
| 原任务 | 3/3 | 100.00% | 100.00% | 0.00% | **66.67%** | 2/3 |
| group_01 | 3/3 | 0.00% | 0.00% | 0.00% | **0.00%** | 0/3 |
| group_02 | 3/3 | 0.00% | 100.00% | 100.00% | **66.67%** | 2/3 |
| group_03 | 3/3 | 0.00% | 50.00% | 0.00% | **16.67%** | 0/3 |

PDDL按两份要求计划的有效比例评分，只验证动作合法性和全部目标，不要求参考序列、步数或最优性。

## 固定版本、模型和材料

- 条件original-skill；模型Tatu GPT-5.2/xhigh；每请求输出上限16384；每槽位累计60父迭代，guard最多1次且共享额度，无子Agent。
- 原题及group_01/02/03各3次，全部正常FAIL/0分保留，不挑最好一次，不用泛化成绩修复或选版。
- 数据固定[556fd216287be7e58480ed5a6dd935ca3370e639](https://github.com/linyouxue/skill-repair-benchmark/tree/556fd216287be7e58480ed5a6dd935ca3370e639/pddl-airport-planning)。本目录original_skill/为执行时冻结的完整原bundle，支持文件和许可完整，没有改Skill。
- OpenHands CLI `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools `1.28.1`；统一本地BenchmarkExecutor保留已有runtime/guard/代理接线改动。
- 这是原Skill baseline，不存在诊断/修复模型、人工修订、样本专用规则或修复增益。submission.json为全部原始执行索引，不伪造Gold诊断/修复提交或after轨迹。

## 原生证据与真实产物

```text
baseline/
├── README.md / submission.json / STATUS.csv / summary.csv
├── original_skill/           # 完整原Skill与支持文件/许可
├── original_runs/<native-run-id>/
│   ├── executor_request.json / result.json / benchmark_result.json
│   └── trajectory/acp_trajectory.jsonl
├── canonical-slots.json / scoring-summary.json / artifact-index.json
├── acceptance.json / protocol.json / evidence-assets.json
└── trajectory_timelines/     # 仓库官方脚本生成，不手改索引
```

[下载本任务完整原生证据](https://github.com/linyouxue/skill-repair-benchmark/releases/download/pddl-flink-gpt52-baseline-20261030/pddl-airport-planning-original-skill-tatu-gpt52-20261030.tar.gz)。
原生config/result、ACP、ATIF和评分在original_runs/；完整LLM请求响应、usage、全部保留运行段和实际/app tar在无损归档。
PDDL实际计划或Flink实际Java/JAR/输出来自各run的artifacts/pre-verifier-workspace.tar.gz，不从摘要补造。
STATUS.csv列全部12次和精确run ID；canonical-slots.json定位有效评分/补验来源。归档路径沿用runs/official-tatu-gpt52/与slots/，通过artifact-index.json关联。

基础设施故障不冒充模型0分；生成中断优先原会话/剩余额度接续，只有评分/导出故障复用同次真实产物补验。
废弃的基础设施失败包仅保留运行标识、原因、调用量和费用简记；有效接续所需的真实前段保留。正常FAIL/0分与有效补验sidecar不变，不增加有效样本数。
完整Skill正文注入、原生评分、真实归档、预算和显式Verifier代理已验收；n_skill_invocations=0的条目有实际完整正文预载证据，callback不是wire dump。
执行器cost仅为估算，提供商实际扣费未知。

按仓库evaluation/results/export_trajectory.py先--dry-run再转换，全部原生轨迹保留；Markdown只是官方可读视图，未截断/改写原始LLM归档。
本次整理新增模型/裁判调用0；按用户要求更新本任务results/README.md成绩表，原有提交约束保留；未改其他方法目录，也不包含JPG实验。两个任务共24个有效槽位，当前目录只统计本任务12条。
