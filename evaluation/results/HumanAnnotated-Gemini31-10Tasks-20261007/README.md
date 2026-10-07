# Gemini 3.1 Pro 十题 cross_model_consistent 验证结果

这10题用于验证 **cross_model_consistent（跨模型缺陷机制一致性）**：以此前Claude和GPT的人工标注、原始轨迹及成功修补为参照，检查相同Skill缺陷在Gemini中的表现，并使用适用的已有修补候选验证修补效果。

本目录统一保存Gemini的官方原版、60轮候选验证，以及后续100/200轮fresh复验结果、完整轨迹和失败机制对照。`cross_model_consistent`对应已有原子defect的跨模型机制；运行PASS/FAIL与停止原因在下表分别记录。

|阶段|有效运行|PASS / FAIL|结果入口|
|---|---:|---|---|
|官方原版，60轮上限|10|1 / 9|[原始汇总](evidence/official-original-summary-20261006.md)|
|候选验证，60轮上限|9|1 / 8|[逐题结果](STATUS.csv)|
|同候选fresh，100轮上限|6|1 / 5|[100轮复验](budget100-20261007/README.md)|
|失败题单次fresh，100/200轮上限|5|0 / 5|[后续复跑](budget-followup-20261007/README.md)|

各阶段选中任务不同，结果分别统计。Video在60轮候选验证中由8/9变为9/9；Scala在100轮fresh中实际67 parent后通过10/10，随后尾部被判stuck。任务评分与停止原因分别记录。

- 模型：`openrouter/google/gemini-3.1-pro-preview`。
- 独立Gold：仅Video的1题1缺陷，8/9→9/9；Gemini/Claude同一机制有证据，GPT同机制未确证，`model_sensitivity=null`。
- 原版2份、修补6份基础设施无效/中断尝试单独记录，不当正常FAIL。
- 费用未知，`null`。

## 实验判断：Gemini与OpenHands不适配

**本批实验的判断是：Gemini与OpenHands的工具调用方式不适配，这是重复操作和预算耗尽的重要原因，后续Gemini实验优先使用Gemini CLI。**

Gemini反复发出不符合终端约束的调用，工具报错或拒绝后，反馈完整返回，但模型没有稳定纠正，继续重复、换一种近似错误调用或局部探索，最终触发停滞检测或用尽轮数。提高预算没有解决这种调用模式。

```text
Gemini生成调用 → 工具执行报错或拒绝调用形态 → 反馈返回模型 → 模型重复动作或继续局部探索 → stuck检测触发或parent预算耗尽
```

Seismic还有合法等待被同动作检测提前截止的情况，需与无效调用循环区分。详见[工具接口及停滞分析](budget-followup-20261007/HARNESS_ANALYSIS.md)与[60→100→复跑比较](budget-followup-20261007/evidence/summary-60-100-followup-20261007.md)。

[失败原因与模型能力分析](FAILURE_ANALYSIS.md) · [逐题结果表](STATUS.csv) · [逐文件来源与结果清单](MANIFEST.json) · [正式Gold](gold.json) · [submission](submission.json)

## 协议与审查

OpenHands CLI commit `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools 1.28.1，Docker任务。初始上限60 parent；后续仅选中任务的worker改为100/200，上述候选与冻结task/verifier保持一致。32768 max output、`reasoning_effort=null`沿模型/SDK默认。每Step最多一次text-only continuation且共享parent预算；provider请求数与parent轮数分别统计。固定两题批次，官方原Skill从冻结任务环境取出，完成全部原版后才比较与修补。

真实canonical结果、ACP、LLM、trainer-facing `results.jsonl`、usage、Skill正文注入与实际产物已在campaign健康/因果审计中核查。此前独立健康审查结果随包保存；不因打包重新执行模型或verifier。原版与fresh均保留冻结官方评分，候选FAIL及旧Gold机制未触发的记录也公开。

## 文件结构

```text
HumanAnnotated-Gemini31-10Tasks-20261007/
  README.md / FAILURE_ANALYSIS.md / STATUS.csv / MANIFEST.json
  submission.json / gold.json / gold_repairs.json
  evidence/                         原始对照、审计、infra、收束与归档收据
  tasks/<task-id>/
    original_skill/                 实际官方运行的完整冻结bundle
    original_run/                   10份原版完整ACP/LLM/results及原评分
    repaired_skill/                 9份实际已验证候选完整bundle，包含有效FAIL
    repaired_run/                   9份fresh完整ACP/LLM/results及原评分
    candidate_review/               已有修补说明与差异
  trajectory_timelines/
    before/                         10份可读原版轨迹
    after/                          9份可读候选轨迹
    trajectory_timeline_index.json  仓库官方脚本导出的索引
  budget100-20261007/               6份100轮复验及独立轨迹索引
  budget-followup-20261007/         5份100/200轮复跑、比较与接口分析
```

可读轨迹使用仓库`evaluation/results/export_trajectory.py`生成。原ACP与LLM保持直接执行证据；`results.jsonl`保留完整训练行。真实预verifier归档及诊断也保存，无从轨迹重建产物。重复agent/trainer轨迹、安装日志和评分目录重复MP4不另存；真实输出MP4位于原预verifier tar，省略文件哈希见MANIFEST。

`MANIFEST.json`将本机source run与上述可移植目录逐项映射。原run metadata和历史审查内绝对路径未改写，保留provenance；审查原文内提及的历史本机路径用该清单及`evidence/`定位。Gold和submission的主要bundle/run字段已改为本目录相对路径。必要credential redaction如有发生会逐文件明确记录，原本机证据不改动。

## 解释限制

PDDL原版PASS无需修补，其空预评分tar是runner路径归档缺口；真实输出从停止容器恢复，单独标记`retained-container-recovery`，不能冒充预评分导出。Seismic/Enterprise候选空tar则是正常未提交文件，不能一概当导出故障。

Azure原版实际20/22，fresh21/22，官方reward仍0；CTRF聚合为四类，参数级stdout才是22项计数。剩余契约争议保留，不借用旧Claude修改契约后的22/22。Shock的原生接口未确证限制仍保留。单次fresh的变化包含预算与路径差异，不能独立估计预算收益或跨模型能力排名。

本机任务必要实际产物已经归档，所属停止容器/零引用任务镜像按实际收据精确清理；清理数及逻辑/物理空间边界见各阶段`evidence/`。本批复验与巡检已结束，活动rollout为0。

## 后续预算复验（2026-10-07）

上述10题官方原版与60轮候选记录保留为初始批次。新增复验继续使用同一完整候选和冻结task/verifier，分别保存在本目录下：

- [六题100轮fresh复验](budget100-20261007/README.md)：1 PASS / 5 FAIL；Scala实际67 parent后通过10/10，尾部stuck与任务评分分别记录。
- [五题100/200轮单次复跑](budget-followup-20261007/README.md)：0 PASS / 5 FAIL；此前stuck的失败题仍设100，此前实际耗尽100的失败题设200；Scala已PASS，未复跑。
- [60→100→复跑比较](budget-followup-20261007/evidence/summary-60-100-followup-20261007.md)与[工具接口及停滞原因](budget-followup-20261007/HARNESS_ANALYSIS.md)。

两个子目录各有独立submission、MANIFEST、完整候选、原始轨迹、官方评分、审查与真实产物。LLM与训练行以gzip保存原字节，ACP和可读Markdown保持直接可读。Shock100、RaR200、Shock200的控制面失败原记录与零模型原verifier补验的派生评分分别保留，评分来源由各子目录MANIFEST明确索引。初始Gold保持原样。
