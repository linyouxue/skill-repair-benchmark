# SkillsBench 15-task 人工 Gold 数据

本目录按 `evaluation/data/core25` 的同一组织方式发布当前评测范围：**15 个 Ground Truth 任务、32 个 defect**。后续诊断、修复与实验数据只评测这 15 个任务。数据版本为 `manual-gold-defects-20260927-v26`。

## 范围

- `gold.json`、提交模板与 `task_status.csv/json` 只包含选定的 15 个任务。
- 15 个任务共包含 32 个 curated defect / repair requirement。
- 未入选任务不属于当前评测范围；目录中可能保留其历史 bundle 或审计材料，但任何后续评测都不得从这些历史材料扩展任务集合。
- `exclusions.json` 是此前 87-task 审计留下的历史记录，不是当前评测任务入口。

## 文件与目录

| 文件 | 用途 |
| --- | --- |
| `gold.json` | 评测器读取的 15-task / 32-defect Gold；保留 `original_bundle` 与 task context |
| `gold_repairs.json` | 与 32 个 defect 对应的人工 RI / Gold repair 清单 |
| `bundle_sources.json` | Original / reference 相对路径、冻结来源和 reference 验证边界 |
| `originals/<task_id>/skills/` | 当前 15 个任务的完整 Original Skill bundle；其余目录为非活动历史材料 |
| `originals/<task_id>/prompts.json` | 当前 15 个任务的原始 task prompt；其余目录为非活动历史材料 |
| `references/<task_id>/skills/` | 当前 15 个任务冻结的人工 reference repair bundle；其余目录为非活动历史材料 |
| `submission.template.json` | 15-task 方法提交模板 |
| `submission.gold-reference.json` | Gold diagnosis + reference bundle 的一致性自测输入 |
| `submission.original-input-check.json` | Original bundle dry-run 输入检查 |
| `task_status.csv/json` | 当前 15-task 范围的状态、代表 run 和 results 引用 |
| `exclusions.json` | 先前 87-task 审计的历史 benchmark-side 问题记录 |

当前 15-task 清单引用 Original Skill 文件 **107** 个（876,131 bytes）、reference Skill 文件 **101** 个（881,438 bytes）和 prompt 文件 **15** 个（26,204 bytes）。

## 与 results 的关系

本目录提供诊断/修复评测所需的 Gold、Original/reference Skill 和任务上下文；执行轨迹不重复复制。代表运行证据统一来自 `evaluation/results/Opus47-OriginalSkill-79Tasks-20260920`，并由 `task_status.json` 的 `results_ref` 精确指向每个 Opus 4.7 selected run；只有该文件列出的 15 个任务属于当前范围。

## Reference 边界

`references/` 是人工标注阶段冻结的参考修复 bundle，用于 Gold/reference 自测，**不等于每个任务都已在同一协议下 canonical fresh-PASS**。具体 validation status 与 source notes 写在 `bundle_sources.json` 和 `gold_repairs.json`；例如 verifier-only、guard-enabled、task-spec-verifier-blocked、joint-validation 等边界均保留，不应被 reference 的存在覆盖。

## 使用

参评方法复制 `submission.template.json`，填写 `method_id`、逐任务 `diagnoses`，并把完整修复后 Skill bundle 放在模板所指 `tasks/<task_id>/skills/`。`benchmark_version` 必须保持 `manual-gold-defects-20260927-v26`。评测器读取本目录的 `gold.json`，并严格要求提交任务集合与这 15 个任务完全一致。

`submission.gold-reference.json` 仅用于检查 Gold 与冻结 reference 的一致性，不是参评方法成绩；`submission.original-input-check.json` 仅供 dry-run 检查 Original 输入。
