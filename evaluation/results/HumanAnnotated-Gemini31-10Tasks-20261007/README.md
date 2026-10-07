# 发现gemini好像和openhands不太适配，也许不太能用openhands,后面要用gemini跑实验的话可能还是要用Gemini CLI,下面是失败模式
```text
Gemini 生成工具调用 → OpenHands 正常执行，但命令报错/参数格式不兼容 → 错误反馈完整返回给 Gemini → Gemini 没有稳定纠正，反而重复、换一种近似错误调用或继续局部探索 → OpenHands 的 stuck detector 触发 / parent budget 耗尽
```

# Gemini 3.1 Pro 十题人工证据验证

本目录保存10题官方原版、9题已审核候选fresh验证及逐题失败机制对照。它是十题证据集，**不是十题Gold集**，也不是匹配条件下的三模型能力排名。

- 模型：`openrouter/google/gemini-3.1-pro-preview`。
- 官方原版先完成：10题有效，**1 PASS / 9 FAIL**。
- 9题有效fresh候选验证：**1 PASS / 8 FAIL**；6题达到60次parent预算。
- 独立Gold：仅Video的1题1缺陷，8/9→9/9；Gemini/Claude同一机制有证据，GPT同机制未确证，`model_sensitivity=null`。
- 原版2份、修补6份基础设施无效/中断尝试单独记录，不当正常FAIL。
- 费用未知，`null`；本次打包/分析/上传没有新付费实验调用。

[失败原因与模型能力分析](FAILURE_ANALYSIS.md) · [逐题结果表](STATUS.csv) · [逐文件来源与结果清单](MANIFEST.json) · [正式Gold](gold.json) · [submission](submission.json)

## 协议与审查

OpenHands CLI commit `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools 1.28.1，Docker任务，60 parent、32768 max output、`reasoning_effort=null`沿模型/SDK默认。每Step最多一次text-only continuation且共享parent预算。固定两题批次，官方原Skill从冻结任务环境取出，完成全部原版后才比较与修补。

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
```

可读轨迹使用仓库`evaluation/results/export_trajectory.py`生成。原ACP与LLM保持直接执行证据；`results.jsonl`保留完整训练行。真实预verifier归档及诊断也保存，无从轨迹重建产物。重复agent/trainer轨迹、安装日志和评分目录重复MP4不另存；真实输出MP4位于原预verifier tar，省略文件哈希见MANIFEST。

`MANIFEST.json`将本机source run与上述可移植目录逐项映射。原run metadata和历史审查内绝对路径未改写，保留provenance；审查原文内提及的历史本机路径用该清单及`evidence/`定位。Gold和submission的主要bundle/run字段已改为本目录相对路径。必要credential redaction如有发生会逐文件明确记录，原本机证据不改动。

## 解释限制

PDDL原版PASS无需修补，其空预评分tar是runner路径归档缺口；真实输出从停止容器恢复，单独标记`retained-container-recovery`，不能冒充预评分导出。Seismic/Enterprise候选空tar则是正常未提交文件，不能一概当导出故障。

Azure原版实际20/22，fresh21/22，官方reward仍0；CTRF聚合为四类，参数级stdout才是22项计数。剩余契约争议保留，不借用旧Claude修改契约后的22/22。Shock的原生接口未确证限制仍保留。当前只有一次候选fresh PASS，不声称组件独立效果或重复稳定性。

本机任务必要实际产物已经归档，所属停止容器/零引用任务镜像按实际收据精确清理；清理数及逻辑/物理空间边界见`evidence/`。Gemini巡检已暂停，活动rollout为0；其他工作流未改变。
