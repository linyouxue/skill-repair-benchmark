# Gemini 3.1 Pro 六题100轮复验

1 PASS / 5 FAIL。沿用父目录60轮试次的完整已审核候选；本批是fresh运行，候选、冻结task/verifier和SDK停滞检测保持原实验条件。

[逐题结果](STATUS.csv) · [文件与评分来源](MANIFEST.json) · [运行清单](submission.json) · [可读轨迹索引](trajectory_timelines/trajectory_timeline_index.json)

|任务|结果|测试|parent上限|实际parent/provider|停止|
|---|---|---|---|---|---|
|[python-scala-translation](tasks/python-scala-translation/repaired_run)|PASS|10/10|100|67/68|stuck|
|[flink-query](tasks/flink-query/repaired_run)|FAIL|1/3|100|33/33|stuck|
|[reserves-at-risk-calc](tasks/reserves-at-risk-calc/repaired_run)|FAIL|1/5|100|100/100|max_iterations|
|[seismic-phase-picking](tasks/seismic-phase-picking/repaired_run)|FAIL|1/2|100|43/43|stuck|
|[shock-analysis-supply](tasks/shock-analysis-supply/repaired_run)|FAIL|2/9|100|100/100|max_iterations|
|[enterprise-information-search](tasks/enterprise-information-search/repaired_run)|FAIL|1/3|100|27/27|stuck|

固定模型 `openrouter/google/gemini-3.1-pro-preview`；OpenHands CLI commit `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools 1.28.1；32768输出、`reasoning_effort=null`沿SDK默认。预算仅本worker改变，共享默认60保留。每Step最多一次text-only continuation并共享parent预算；provider请求数包括重试等，不能当parent轮数。

每个 `tasks/<task>/repaired_skill` 是实际运行时完整候选snapshot。`repaired_run` 保存原始ACP、压缩LLM/训练行、配置、结果、真实产物及原verifier输出；`evidence` 保存已完成独立健康/机制审查及精确清理收据。费用未知为null。

控制面失败与任务评分分别保留：Shock100、RaR200、Shock200使用真实产物的零模型冻结原verifier补验；恢复评分以明确派生的 `verifier-recovery-20261007/recovered-summary.json` 为准，原始infra结果保持原样。可读轨迹中的原始infra元数据不是补验后的有效任务分数。

[60→100比较](evidence/summary-60-vs100-20261007.md) · [重复操作原因](evidence/stuck-root-cause-20261007.md) · [后续单次复跑](../budget-followup-20261007/README.md)

Scala67轮后通过10/10，随后stuck；停止原因与评分独立。该单次fresh的改善同时包含更多预算和不同路径，不能独立估计预算因果收益。
