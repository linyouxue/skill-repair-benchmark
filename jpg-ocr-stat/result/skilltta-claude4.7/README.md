# SkillTTA / Claude Opus 4.7 AIGW (Tatumass)

- 最终 Skill 版本：`skilltta-opus47-aigw-jpg-v2`，已冻结；执行器规范化 bundle 哈希为 `sha256:d477760d2d0c1da2196b027a473f0174194bae28803824eceed8f2bee394844f`。
- 方法与代码版本：SkillTTA retrieval + synthesis，37 个多模态诊断窗口与两轮迭代修复。完整五 Skill bundle 位于 `skills/`；方法最终修改涉及 `image-ocr/SKILL.md` 与 `xlsx/SKILL.md`。
- 实际模型与配置：诊断、修复和三次最终执行均为 Tatumass Anthropic-compatible `claude-opus-4-7@AIGW-default`，登记 base URL `https://maas.tatucloud.com/v1`。最终执行使用 OpenHands CLI/SDK/Tools 1.28.1；ACP agent 不支持显式 reasoning-effort，因此记录为 `null`。每次根 Agent 上限为 65 parent iterations。
- 修复材料与版本：只使用原 22 张票、原任务、原 Skill 与 `jpg-ocr-stat/diagnosis` 允许的反馈。37 次诊断请求以及两次修复请求均实际发送 22 个 `image/jpeg` 内容块；未读取 oracle 值、verifier 断言或扩展泛化组。
- 方法内部新增执行：完整请求、响应、图片块审计、覆盖记录、综合诊断及两轮修复记录见 `evidence/repair/`。
- 三次最终执行与原 Excel：同一冻结 Skill 分别从任务初始状态独立运行。`r012` 为 23/65、自然 `end_turn`、44/44；`r022` 为 32/65、自然 `end_turn`、42/44；`r023` 为 24/65、自然 `end_turn`、44/44。原 Excel、ACP/LLM 轨迹与评分记录分别位于 `evidence/final_runs/run_01/`、`run_02/`、`run_03/`。
- 必要披露：人工参与仅限 adapter/执行器兼容修复、运行监控与证据整理，没有人工修改最终 Skill 或三次原 Excel。Skill 保留了方法从本任务诊断形成的通用 OCR/表格规则。`r022` 首次 verifier 执行因 uv 环境脚本路径缺失而失败；随后对该次原 Excel 使用相同官方字段评分脚本做 verifier-only 重试，模型调用为 0，原失败日志和重试记录均保留。后续未见图片泛化评测不属于本目录；`group_02` 已按独立规范执行三次，材料见 `jpg-ocr-stat/evaluation/results/methods/skilltta-claude4.7/`。
- 证据入口：`evidence/README.md`。历史基础设施失败及较早运行保留于 `evidence/attempts/`，但不计入以下三次均值。

| 评测集合 | 第1次字段正确率 | 第2次 | 第3次 | 三次均值 |
|---|---:|---:|---:|---:|
| 原22张小票（每次44字段） | 1.000000（44/44） | 0.954545（42/44） | 1.000000（44/44） | 0.984848（130/132） |

三次原 Excel SHA-256：

- `run_01`: `7a04ae43216f4a55c2d325d52780b1c3af335a4ca97be184078b2bc60d032972`
- `run_02`: `1c4c48a2283c57d92acd173b4836f79fb28e83a9eac6d656e6c6ed0b1bbd8202`
- `run_03`: `7af42066133f39fad61ecc2922d60bba393c897dff4bf062c93118c145a5f285`
