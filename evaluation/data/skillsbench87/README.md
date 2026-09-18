# SkillsBench 87-task 人工审计数据

本目录是 SkillsBench 87 个任务的人工审计快照，用于说明哪些任务无需 Skill 修复、哪些任务进入 Ground Truth，以及哪些任务因 benchmark-side 问题暂不纳入。

## 当前闭环

- 总任务数：**87**
- 官方 Original Skill 可通过：**48**
- 进入 Ground Truth：**31 个任务 / 57 个 Gold defects**
- 暂不纳入：**8**

三类互斥且覆盖 87/87。代表运行来自 [`evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916`](../../results/GPT52-AllTasks-RepresentativeRuns-20260916)，模型统一为 GPT-5.2；`guard_used=true` 的通过运行保留该标记，不与 guard-off 运行混淆。

## 文件

- `task_status.csv`：87 行人工审计状态，适合快速浏览和统计。
- `task_status.json`：同一状态的结构化版本，包含代表 run、results 引用和 Gold defect 数量。
- `gold_defects.json`：31 个 Ground Truth task 的 57 个 curated defect；不复制官方 Skill bundle。
- `gold_repairs.json`：与 57 个 defect 对应的人工 Gold repair requirements。
- `exclusions.json`：8 个暂不纳入任务及 benchmark/task/oracle/verifier/template 问题和建议修复方向。

## 分类口径

`original_skill_pass` 表示使用官方 Skill 的代表运行通过，因此不作为 Skill repair case。`ground_truth` 表示 Original Skill 失败且人工审计确认存在可归因的 Skill defect。`excluded_benchmark_issue` 表示存在更上游的 benchmark 定义/验证冲突，当前失败不能干净归因为 Skill。

这里不重复存放执行轨迹；每个任务通过 `results_ref` 指向 `evaluation/results/` 中已经归档的原始执行证据。
