# flink-query：官方原Skill / Tatu GPT-5.2 baseline

有效 **12/12**，平均reward **0.318250731495**，严格全对 **0/12**。
2026-10-30完成原12条验收；2026-11-03按用户要求替换三条提前结束的运行，其余九条不变。

| 数据集 | 有效次数 | 第1次 | 第2次 | 第3次 | 均值 | 全对次数 |
|---|---:|---:|---:|---:|---:|---:|
| 原任务 | 3/3 | 74.09% | 74.09% | 0.00% | **49.40%** | 0/3 |
| group_01 | 3/3 | 44.95% | 44.95% | 0.00% | **29.97%** | 0/3 |
| group_02 | 3/3 | 46.90% | 46.90% | 0.00% | **31.27%** | 0/3 |
| group_03 | 3/3 | 50.00% | 0.00% | 0.00% | **16.67%** | 0/3 |

Flink按正确输出正例、正确排除负例及额外错误项评分。7次非零运行的positive_job_accuracy均为1，但负例过滤未全对；其余5次原生0分照实计入。

## 固定版本、模型和材料

- 条件original-skill；模型Tatu GPT-5.2/xhigh；每请求输出上限16384；每槽位累计60父迭代，guard共享额度，无子Agent。九条沿用guard1；原题r02、原题r03、group_03-r03因原运行提前结束，选入guard3独立重评并替换。
- 原题及group_01/02/03各保留3条当前结果。这是九条guard1加三条按早停选中的guard3重评，不是统一guard3的12次随机baseline；正常新0分也替换，不按高分选版，不用泛化成绩修复Skill。新旧差异不能全部归因于guard。
- 数据固定[556fd216287be7e58480ed5a6dd935ca3370e639](https://github.com/linyouxue/skill-repair-benchmark/tree/556fd216287be7e58480ed5a6dd935ca3370e639/flink-query)。本目录original_skill/为执行时冻结的完整原bundle，支持文件和许可完整，没有改Skill。
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

[下载本任务完整原生证据](https://github.com/linyouxue/skill-repair-benchmark/releases/download/flink-baseline-guard3-replacement-20261103/flink-query-original-skill-latest12-20261103.tar.gz)（精确大小与SHA见evidence-assets.json）。
原生config/result、ACP、ATIF和评分在original_runs/；完整LLM请求响应、usage、全部保留运行段和实际/app tar在无损归档。
PDDL实际计划或Flink实际Java/JAR/输出来自各run的artifacts/pre-verifier-workspace.tar.gz，不从摘要补造。
STATUS.csv列全部12次和精确run ID；canonical-slots.json定位有效评分/补验来源。旧九条归档沿用runs/official-tatu-gpt52/与slots/；新三条使用runs/official-tatu-gpt52-guard3-replacement/与slots/，通过artifact-index.json关联。被替换旧三条仅在本地保留，Git历史不改。

基础设施故障不冒充模型0分；生成中断优先原会话/剩余额度接续，只有评分/导出故障复用同次真实产物补验。
有效补验sidecar优先；原本未归档的早期故障文件如实缺失，不补造。新三条中两条遇到上游故障，均沿原会话、同工作区与剩余预算恢复，历史请求及费用并入有效样本；已合并的中断包装不重复保留，不增加样本数。

新原题r02、group_03-r03保留原ACP前缀、混合续段、完整原生SDK事件和合并LLM；原始ATIF仅覆盖ACP前缀，另附明确标记为派生的完整SDK ATIF视图。它们的partial_trajectory=true、training_ready=false保持不变：原生评分有效，训练数据隔离，不能称为完整原始ACP或SFT就绪。
原生恢复的原始base_state checkpoint文件未保留；journal计数/usage汇总、各续段计数收据和真实LLM配置证据仍在，不能用这些摘要冒充完整checkpoint原件。
完整Skill正文注入、原生评分、真实归档、预算和显式Verifier代理已验收；n_skill_invocations=0的条目有实际完整正文预载证据，callback不是wire dump。
执行器cost仅为估算，提供商实际扣费未知。

按仓库evaluation/results/export_trajectory.py先--dry-run再转换，全部原生轨迹保留；Markdown只是官方可读视图，未截断/改写原始LLM归档。
本次整理新增模型/裁判调用0；按用户要求更新本任务results/README.md成绩表，原有提交约束保留；未改其他方法目录，也不包含JPG实验。当前目录只统计本任务12条；本次仅替换指定三条baseline及相关索引/证据，不发布人工Skill评测结果，不修改PDDL或其他方法。
