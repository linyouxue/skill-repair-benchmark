# Data split, validation, and selection

## 实际数据使用

本实验没有跨任务训练，也没有设置独立 train/validation/test task split。

- 优化输入：每个任务自己的原始失败 baseline 结果，以及该任务前序失败 gate 的结果。
- 候选生成：对同一任务的 Skill bundle 进行诊断和 rewrite。
- 候选验证：再次执行同一个任务。
- 最终选择：同一任务 gate 的 pass/comparable/reward 用于 keep/revert。
- 最终报告：所选 gate 结果同时被用作该任务当前实验结果。

因此这里存在明确的 same-task gate leakage。`repair_loop.json` 与
`method_result.json` 均记录了 `same_task_gate` / `same_task_gate_leakage`。当前结果不是
held-out validation estimate，也没有独立最终测试集。

## 跨轮机制

每个任务最多 R=2：

1. round 1 读取 baseline 失败证据，生成诊断与候选 Skill；
2. gate 执行候选；
3. 只有可比性改善、reward 提升或从 fail 变 pass 时才 `keep`；否则 `revert`；
4. 被拒提案写入 `rejected_buffer`；失败 gate 写入 `failure_evidence`；
5. round 2 从当前 `best_skill` 继续，并读取所有历史失败证据和 rejected buffer；
6. 若某轮通过则提前停止，否则完成两轮后输出 gate 选出的 `best_skill`。

本包共有 85 个实际执行的 round：61 次 revert，24 次 keep。所有 round 都可通过
`metadata/TASK_ROUND_INDEX.json` 映射到其候选包、rollout 和 verifier。

## “训练/验证/最终测试”对应关系

若必须按三分法描述：

- 训练/优化证据：该任务 baseline + 已发生的失败 gate 结果；
- 验证：同一任务 gate；
- 最终测试：未设置独立 final test。

标准 submission 已整理，但本包没有额外运行一个独立 held-out final evaluation。

