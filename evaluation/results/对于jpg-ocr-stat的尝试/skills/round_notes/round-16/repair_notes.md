# Round 16：修正公开 task hint 冲突并强化剩余执行缺口

用户明确授权修正 GST 排除、下一行末数字这两条公开 task hint，并针对 Round 15
轨迹中的其他问题强化英文 Skill，再运行一次 GPT-5.2。

## Task 提示修改

本轮从此前实际执行的 `/home/linyuanjing/skillsbench-v1.1/tasks/jpg-ocr-stat`
复制完整任务到 `task-variant/tasks/jpg-ocr-stat`，仅修改该副本的 `task.md`：

1. 跨行取值必须有版面、标签及上下文绑定，不能仅按“下一行最后一个数字”选择。
2. GST/TAX/SST 等关键词是其他金额字段的识别线索，不是整行无条件排除规则；
   含税的最终应付字段仍须按最终应付语义处理。

上游原任务和旧轮次不改；verifier、oracle、收据数据、环境及输出 schema 沿用。
这两项是公开提示冲突的修正，不表示已证明官方隐藏答案或 verifier 正确。

## Skill 修改依据

仅调整新增七条中的第 1、4、5、6、7 条；第 2、3 条及官方原正文保留。

| Round 15 的可观察问题 | Round 16 强化 |
|---|---|
| 请求 5：首个非空 date/amount 即赋给 best 值，两者非空就返回 | 显式区分 candidate / unresolved / confirmed；必须证据支持才确认，非空不构成结束条件 |
| 请求 11：可疑标签数量为零就认为无需继续检查；未实际局部识别 | 按抽取路径和证据建立 review queue，对疑点实际 crop OCR 或查看对应原图区域，保存裁决 |
| first-found 候选阻断后续更强证据纠错 | 只保护证据确认后的字段；未确认候选保留更新路径 |
| 全部图片完成后才一次性保存证据 JSON | 每图首轮记录、未决项及每次局部裁决均增量落盘 |
| 重开文件后主要核验非空、格式、行列数和排序 | 审核字段确认依据、复核记录、未决数量，并逐字段对照实际 Excel 与确认记录 |

不增加票据特定答案、固定 OCR 投票次数或全批反复运行；不修改执行器。

## 验证设置与解释边界

- Rollout：`jpg-ocr-stat-round-16-r001`，一次 fresh development rollout。
- GPT-5.2 / OpenRouter；reasoning effort 保持 `None`；60 iterations；guard 开启。
- 原代理注入和同 commit 本地 OpenHands runtime 沿用；复用本地任务镜像。
- 本轮同时修改 task hint 和 Skill，是修改任务提示后的诊断实验。无论是否通过，
  都不能当作“未修改官方 task 的通过”，也不能将收益单独归因于 Skill 修改。
- 隐藏 verifier 答案不用于修补；实际结果待用户通知结束后验收，不预先升级 Gold。

启动已确认：task container `jpg-ocr-stat-round-16-r001-main-1` 为 Up，使用本地
`bf__jpg-ocr-stat` 镜像；输入 Skill 快照与 Round 16 英文候选一致。停止监控，
用户通知完成后再检查评分及轨迹。

## 结果

`jpg-ocr-stat-round-16-r001` 已完成：reward 1，官方 verifier 1/1，execution_ok=true，
结构 validator healthy=true。29/60 iterations，30 次 provider 请求，27 次工具调用；
总耗时 1440.7 秒，成本 $0.7683466。实际 provider response 的 `instructions` 中
包含本轮英文 Skill，不能因归一化 `request.body.messages` 只显示 task 就误判未注入。

本轮只记录为修改 task 提示后的诊断性 fresh-agent 通过，不能直接提升为原始
task 的 Skill-only Gold。`artifacts/` 仍为空，不能独立重放真实工作簿；详情见
`annotation.md` 的 Round 16 r001 验收。
