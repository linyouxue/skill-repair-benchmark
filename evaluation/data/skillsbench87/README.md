# SkillsBench 87-task 人工 Gold 与审计数据

本目录按 `evaluation/data/core25` 的同一组织方式发布当前完整人工 Gold：**31 个 Ground Truth 任务、57 个 defect**，并保留 87-task 审计闭环（48 个 Original-Skill PASS、31 个 Ground Truth、8 个 benchmark-side exclusion）。数据版本为 `manual-gold-defects-20260917-v25`。

## 范围

- 87 个任务全部有 `task_status.csv/json` 状态。
- 48 个任务使用官方 Original Skill 的代表运行可通过，不需要 Skill repair。
- 31 个任务进入 `gold.json`，共 57 个 curated defect / repair requirement。
- 8 个任务因 task/oracle/reference/verifier/template 冲突暂不进入 Gold，详见 `exclusions.json`。

## 文件与目录

| 文件 | 用途 |
| --- | --- |
| `gold.json` | 评测器读取的 31-task / 57-defect Gold；保留 `original_bundle` 与 task context |
| `gold_repairs.json` | 与 57 个 defect 对应的人工 RI / Gold repair 清单 |
| `bundle_sources.json` | Original / reference 相对路径、冻结来源和 reference 验证边界 |
| `originals/<task_id>/skills/` | 31 个 Ground Truth task 的完整 Original Skill bundle |
| `originals/<task_id>/prompts.json` | 31 个任务的原始 task prompt |
| `references/<task_id>/skills/` | 31 个任务冻结的人工 reference repair bundle |
| `submission.template.json` | 31-task 方法提交模板 |
| `submission.gold-reference.json` | Gold diagnosis + reference bundle 的一致性自测输入 |
| `submission.original-input-check.json` | Original bundle dry-run 输入检查 |
| `task_status.csv/json` | 87-task 的 48/31/8 分类、代表 run 和 results 引用 |
| `exclusions.json` | 8 个暂不纳入任务及 benchmark-side 问题 |

Original Skill 文件共 **259** 个（2,746,162 bytes），reference Skill 文件共 **367** 个（5,226,748 bytes），prompts 共 **31** 个（55,579 bytes）。整个目录本次发布共 **666** 个文件、约 **8,577,496 bytes**。

## 与 results 的关系

本目录提供诊断/修复评测所需的 Gold、Original/reference Skill 和任务上下文；执行轨迹不重复复制。`task_status.json` 的 `results_ref` 指向 `evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916` 中的代表运行证据。`sec-financial-report` 使用真实 Original-Skill server run `sec-financial-report-original-skill-server-r003`。

## Reference 边界

`references/` 是人工标注阶段冻结的参考修复 bundle，用于 Gold/reference 自测，**不等于每个任务都已在同一协议下 canonical fresh-PASS**。具体 validation status 与 source notes 写在 `bundle_sources.json` 和 `gold_repairs.json`；例如 verifier-only、guard-enabled、task-spec-verifier-blocked、joint-validation 等边界均保留，不应被 reference 的存在覆盖。

## 使用

参评方法复制 `submission.template.json`，填写 `method_id`、逐任务 `diagnoses`，并把完整修复后 Skill bundle 放在模板所指 `tasks/<task_id>/skills/`。`benchmark_version` 必须保持 `manual-gold-defects-20260917-v25`。评测器读取本目录的 `gold.json`。

`submission.gold-reference.json` 仅用于检查 Gold 与冻结 reference 的一致性，不是参评方法成绩；`submission.original-input-check.json` 仅供 dry-run 检查 Original 输入。
