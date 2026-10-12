# jpg-ocr-stat Round 15

日期：2026-10-08。用户要求在英文七条 guidance 的基础上强化描述，再用 GPT-5.2
尝试一次。本轮仍是单次 fresh rollout，不自动连续搜索至通过。

## 为什么继续强调

Round 14 r002 为有效失败：18/60 iterations、17 次工具调用、18 次正常 provider
响应，已生成和重开 Excel，但官方 `::test_outputs` 失败于逐行内容相等断言。
没有证据表明是极短异常停工、网络或预算耗尽。本轮依据模型生成的解析代码而非
隐藏期望值强化描述：整页小数点标志或数字长度被用来补小数，当前/下一行取最后
数字，非法月份取余，多次全批 OCR，以及只做结构核验就调用 `finish`。

## 修改范围

保留 Round 14 的官方完整 bundle、英文七条结构和官方原始正文，仅强化
`image-ocr/SKILL.md` 开头的人工补充：

| 七条要求 | 强化方式 |
|---|---|
| 字段证据 | 每个已接受值必须有已保存的同字段来源与裁决依据；不支持的候选保持 unresolved |
| 最终应付语义 | 先确定应付字段再选完整数字；行末/下一行位置不证明字段绑定 |
| 数字和日期 | 明确整页小数标志、长度、月份取余/截断都不是纠错依据，须转局部复核 |
| 局部复核 | 非空但依赖弱回退同样必须复核；不是强制投票，而是针对标签和完整数字补证据 |
| 结果稳定 | 保存已确认字段；共享解析逻辑变化须核对受影响记录，不全局静默替换 |
| 增量保存 | 首轮先保存字段/未决项，final save 只消费已保存记录，不嵌入额外全批 OCR |
| 完成检查 | finish 前核查所有字段依据及弱回退已复核，再重开逐行核对工作记录；结构合法不等于内容正确 |

不添加具体票据答案、固定投票次数、helper 程序或额外 solver 提示词。不更改
任务、verifier、执行器、completion guard 行为、迭代预算、模型或代理配置。
这些要求覆盖已观察的执行错误，但不声称 Skill 已穷尽所有错误或能保证通过。

## 验证配置

- ID：`jpg-ocr-stat-round-15-r001`
- Model：`openrouter/openai/gpt-5.2`，reasoning effort 与 Round 14 相同，不显式设置。
- 每 Step 60 parent iterations；completion guard 开启，text-only retry limit 1。
- 1 次 fresh rollout，沿用现有代理注入、任务镜像与 exact-pinned OpenHands archive。
- 原 Round 14 候选、输入快照、轨迹及结果保持不变；结果待验证。

## 启动核查

已确认 `jpg-ocr-stat-round-15-r001-main-1` 运行，复用既有任务镜像；真实运行的
`inputs/skills/image-ocr/SKILL.md` 为 Round 15 英文强化版。仅启动单次 GPT-5.2
rollout，确认容器后停止监控，等待用户通知结束；不声称已通过或模型已完成。

## 验收结果

用户通知结束后核查：reward 0，`execution_ok=true`，官方 `::test_outputs` 0/1，
失败于逐行内容相等断言；14/60 iterations、14 次正常 provider 响应、12 次工具
调用，1035.7 秒，$1.2085871，519011 total tokens。确定性轨迹 validator 为
healthy；5 个 Skill 全文 preload 匹配。guard 使用一次 continuation 后模型重开
Excel，最终真实调用 `finish`；不是只有两步的异常停工。

描述强化有实际影响：金额解析不再使用整页小数标志/长度补位，去掉月份取余，
新增字段来源记录并实际写入 `ocr_evidence.json`，主 OCR 脚本只执行一次。但
`extract_fields_for_image` 在日期、金额首候选非空时立即确认返回，没有 unresolved
状态或 crop 复核；证据记录没有驱动接受/拒绝裁决，最终仍主要核验格式和结构。

同时需披露公开 task hint 与 Skill 之间的冲突：task 提示无条件排除含 GST 的行、
下一行取最后数字，而修补要求字段语义裁决和验证跨行绑定。不能把模型保留这些
task hint 的现象全部当作纯模型能力不足。本轮是有效任务失败，但不是 Skill
强化毫无作用或 verifier 已证实错误。详情和请求/代码位置见 `annotation.md`。

工作簿和证据 JSON 有运行/读取证据，但 `artifacts/` 没有导出真实文件，容器亦
已清理，不能独立 verifier replay；保持原始评分、输入与轨迹，不事后重建。
没有自动修改下一版 Skill、发起下一次 paid rollout 或推送 GitHub。
