# Round 17：旧 Skill + 已修正公开 task hint 的对照

用户要求检查 Round 16 的通过是否可能主要来自 task 描述修正。本轮不再修改
Skill，使用 Round 15 实际 rollout 的完整冻结 `inputs/skills`，而不是把旧正文
手工重写，也不是官方原始 Skill。18 个文件直接复制到本轮 bundle。

Task 直接复用 Round 16 的隔离副本：GST/TAX/SST 不再整行自动排除，跨行取值
必须确认标签与金额属于同一字段。除此之外，任务输入、输出 schema、verifier
及环境均沿用；不修改上游原任务或任何旧轮次。

| 运行 | Task hint | Skill | 已知结果 |
|---|---|---|---|
| Round 15 r001 | 官方原提示 | Round 15 | reward 0 |
| Round 16 r001 | 已修正两条冲突提示 | Round 16 强化版 | reward 1 |
| Round 17 r001 | 与 Round 16 相同 | Round 15 冻结输入原样复用 | reward 0，官方 verifier 0/1 |

## 执行设置

- Rollout：`jpg-ocr-stat-round-17-r001`；只运行一次 fresh 对照。
- GPT-5.2 / OpenRouter；reasoning effort `None`；60 iterations；guard 开启。
- 执行器不改；沿用 runner/build/task/verifier 代理及同 commit 本地 OpenHands。
- 使用已有任务镜像；任务源仍指向 `round-16/task-variant/tasks`。
- 不读取隐藏答案，不注入上轮模型生成的代码、数值或工作簿。

若本轮通过，说明旧 Skill 配合修正后的 task 至少能够通过一次，支持公开 hint
冲突影响结果的解释，不能说明 Round 16 强化是必要条件。若本轮失败，也不能
用一次结果证明 task 修正无效或强化必不可少；仍须考虑模型随机性。
本轮继续属于修改-task 诊断实验，不提前提升原 task 的 Gold。

用户随后询问 Round 14 是否可能通过：Round 14 也覆盖字段证据、GST 和局部
复核，因此不能仅凭措辞简短判断无法通过。本轮仍用 Round 15，是为检验
Round 16 最新强化之前的直接版本；不额外启动 Round 14 付费对照。

启动已确认：`jpg-ocr-stat-round-17-r001-main-1` 为 Up；实际 task digest 与 Round 16
一致，运行输入 Skill 快照与 Round 15 冻结输入一致。停止监控，等待用户通知。

## 结果

用户要求再次查看后确认已结束：reward 0，execution_ok=true，官方 verifier 0/1；
41/60 iterations、41 次成功 provider 响应、40 次完成工具调用。耗时 1627.0 秒，
成本 $0.7504168，validator healthy=true。修正 task hint 在实际 prompt 中，
相关 `image-ocr` 全文在 provider instructions 中，未见终态基础设施异常。

本次“Round 15 Skill + 修正 task”仍失败，而“Round 16 Skill + 同一修正 task”
通过，未支持只改 task 即足够的解释；仍不能排除随机性或证明最新强化必需。
不自动再计费。真实工作簿未导出，不能独立 replay；详情见 annotation.md。
