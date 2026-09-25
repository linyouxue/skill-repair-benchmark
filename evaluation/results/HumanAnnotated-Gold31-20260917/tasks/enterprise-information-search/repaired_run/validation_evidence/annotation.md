# 人工诊断与 Skill 修复标注：`enterprise-information-search`

## 1. 基本信息

| 字段 | 内容 |
|---|---|
| 标注状态 | `closed / Gold repair content-validated / task-spec-verifier-blocked` |
| 标注方式 | `human-verified-ai-assisted` |
| Base model | `openrouter/openai/gpt-5.2` |
| Agent / protocol | `OpenHands / benchmark-executor skillrepair-v1` |
| Task digest | `sha256:57add4050ad2983534267dcc37a8155a29a5e4a305207cfb5b971330f1355d9c` |
| Original Skill bundle digest | `sha256:70515c01f482bbd02f193e88065ddc70da2bae5ddebfc691ca6c1b735f3966f0` |
| Round 1 Skill bundle digest | `sha256:7d35ada691a1b6665faa8334c3e65d5e78b623d7f5c62545653f51a17bd5d938` |
| Original rollout | `enterprise-information-search-original-skill-r002` |
| Repair rollout | `enterprise-information-search-round-1-r001` |
| 证据根目录 | `manual_annotation_runs/enterprise-information-search/runs/manual-annotation/` |

## 2. 功能步骤

| Step ID | 功能步骤 | 预期输出或状态 | 相关 Skill |
|---|---|---|---|
| S1 | 读取三项检索问题并确定目标产品和实体类型 | 明确 q1 的报告作者/reviewer、q2 的洞察提供者和 q3 的 demo URL | `enterprise-artifact-search` |
| S2 | 为 q1 构建并验证报告候选与版本链 | 识别同一报告的 draft、final、latest 及 share/update provenance | `enterprise-artifact-search` |
| S3 | 汇总 q1 的作者与有证据的 reviewer | 同时覆盖文档字段、文档反馈、会议建议、Slack thread 与扁平化同频道反馈 | `enterprise-artifact-search` |
| S4 | 检索 q2、q3 的竞品洞察提供者与 demo URL | 返回完整且去重的 employee ID 和 URL 集合 | `enterprise-artifact-search` |
| S5 | 写入 `/root/answer.json` | 三个 answer 均为 list，并为每题写入 token 计数 | task output contract |
| S6 | 接受官方 verifier 验证 | 答案值与输出 schema 均通过 | task verifier |

## 3. Original-Skill rollout

| Rollout ID | 官方通过 | Reward | 执行证据 | 最早失败步骤 | Failure ID |
|---|---:|---:|---|---|---|
| `enterprise-information-search-original-skill-r002` | 否 | 0.0（4/5） | `execution_ok=true`；`comparable=true`；33/60 iterations；32 次工具调用；完整 Skill persistent preload 已核验 | S3 | F1 |

Original-Skill r002 是有效 fresh rollout，不是提前结束或基础设施故障。模型正确回答 q2、q3，token
字段也通过类型检查；唯一答案错误是 q1 只返回 8/11。它检查了报告文档、文档 feedback 和会议成员，
但在报告 share message 的 `ThreadReplies` 为空后，没有继续检查同频道紧邻的顶层消息，因此漏掉
3 位在该消息后提供具体报告修改建议的 reviewer。

另一个早期 Original rollout 曾在 3/60 iterations 提前结束，只作为随机执行失败背景，不用于
F1 的 Skill 缺陷归因。

## 4. 失败模式与可归因性

| Failure ID | Step | 可观察问题与最早根因 | 根因标签 | 进入 Gold repair | 证据与边界 |
|---|---|---|---|---:|---|
| F1 | S3 | 原 Skill 把 final/latest 文档保留为单一 anchor，并只写了 Slack thread replies；它没有要求保留同一报告各版本上的 reviewer provenance，也没有说明导出数据可能把回复扁平化成同频道顶层消息。模型因此在 thread 为空时过早认定 reviewer 集合完整。 | `skill_missing_guidance` | 是 | Original q1 为 8/11；Round 1 直接执行新增检索分支后达到 11/11，且无答案 ID、日期或消息 ID 硬编码。 |
| F2 | S5 | task 示例把 `tokens` 写成带引号的 `"xxx"`，而 verifier 要求该值为 `int/float`。Round 1 把三个计数写为数字字符串，答案内容虽全部正确，官方 reward 仍为 0。 | `task_or_verifier_issue` | 否 | 官方答案内容测试通过；仅三个 token 类型子测试失败。该问题与 F1 的检索流程相互独立。 |

## 5. Gold repair item

| Repair ID | Tag | Skill 与位置 | Gold repair requirement | 状态 |
|---|---|---|---|---|
| RI-001 | `skill_missing_guidance` | `enterprise-artifact-search/SKILL.md` 的 `Step 3 — Select the correct report version` 与 `Step 5 — Extract key reviewers` | 保留 latest/final 作为内容锚点，同时建立同一报告的版本及 share/update provenance chain；对每条分享/更新消息检查嵌套 thread 和有明确边界的同频道连续反馈；完成文档、Slack、会议 reviewer 证据分支后再结束。 | `content-validated / task-spec-verifier-blocked` |

该修复是通用的跨版本 reviewer 证据完整性规则，没有写入答案 ID、具体日期、消息 ID 或 verifier
期望值。虽然本轮 reward 不是 1，但人工审核确认新增行为被实际采用，且官方答案内容测试精确通过，
因此将 RI-001 纳入 Ground Truth；验证状态不得改写为 `agent-validated`。

## 6. 人工修复轮次

`enterprise-information-search-round-1-r001` 确定性加载了 Round 1 候选 bundle；expected、observed
与输入快照 digest 一致，均为
`sha256:7d35ada691a1b6665faa8334c3e65d5e78b623d7f5c62545653f51a17bd5d938`。

模型识别了同一报告的 draft、final 和 latest 版本，并找到初始分享与 final 更新消息。在发现初始
分享的 `ThreadReplies=0` 后，它按新增规则排序扫描同一频道的连续消息，找回 Original r002 漏掉的
3 位实质反馈者，再与其余作者和 reviewer 证据合并。最终 q1 从 8/11 提升到 11/11；q2、q3
保持正确，官方 `test_answer_structure_and_values` 通过。

本轮使用 46/60 iterations、46 次 provider request、45 次工具调用，`stop_reason=end_turn`；
`execution_ok=true`、`comparable=true`、`protocol_evidence_valid=true`、
`trajectory_complete=true`，没有 API、transport、timeout、iteration-limit、容器、verifier 执行或
export 错误。总耗时 644.5 秒，成本 `$0.67620385`。

官方 pytest 最终为 2 passed、3 failed。三项失败全部来自 `tokens` 类型：模型函数显式返回
`str(...)`，得到 `"42"`、`"19"`、`"23"`；verifier 要求 JSON number。由此本轮只记为
`content-validated / task-spec-verifier-blocked`。

## 7. 证据与验证边界

`n_skill_invocations=0` 表示模型没有调用显式 Skill 工具，但 benchmark-executor 已在首次任务提示前
把完整候选 Skill 确定性写入 persistent AgentContext；expected 与 observed bundle digest 一致，
因此正文暴露成立。轨迹对新增版本链和扁平 Slack 规则存在直接行为证据。

轨迹没有读取 `/oracle`、`/verifier`、测试代码、ground truth 或 gold answer。模型最后用会议
`participants` 构造部分 reviewer 列表，形式上没有严格保持 Skill 的逐人证据门；但它此前已输出完整
会议 transcript，而这些成员均提供了具体建议，因此本轮没有因“参会即 reviewer”引入错误成员。

rollout 顶层 `artifacts/` 为空，存在 evidence-archive gap；不能把轨迹中曾存在的
`/root/answer.json` 冒充为已归档原始产物。答案值与类型的判断来自官方 verifier 日志和完整轨迹。

## 8. 最终标签与人工确认

| 字段 | 内容 |
|---|---|
| Final status | `Gold repair / content-validated / task-spec-verifier-blocked` |
| Gold failure mode | F1：Skill 缺少报告版本链 reviewer provenance 与扁平 Slack 连续反馈检索规则 |
| Gold repair requirement | RI-001，已由直接轨迹行为与官方答案内容测试验证 |
| Independent issue | F2：task 示例与 verifier 的 `tokens` 类型要求冲突 |
| Skill exposure | `explicit invocation=0; persistent full-body exposure verified=true`；候选 digest 完全一致 |
| Direct-use evidence | thread 为空后继续扫描同频道连续消息，并找回 Original 漏掉的 3 位 reviewer |
| Official result | Original r002：reward 0、q1 8/11；Round 1：reward 0、三问答案值精确正确、token 类型 3 项失败 |
| 用量 | Original r002：33 iterations、`$0.4219642`、558.3 秒；Round 1：46 iterations、`$0.67620385`、644.5 秒 |
| Artifact caveat | 顶层 `artifacts/` 为空；仅 verifier 日志和轨迹可复核 |

- [x] 已核对 task、Original Skill、候选 Skill、verifier 与完整轨迹；
- [x] 已确认两次用于归因的 rollout 均为 `execution_ok=true`、`comparable=true`；
- [x] 已确认候选 bundle digest 与实际 persistent preload 一致；
- [x] 已确认模型真实执行新增的版本链与扁平 Slack 检索；
- [x] 已确认 Round 1 三问答案值全部通过官方内容测试；
- [x] 已记录 task/verifier 的 token 类型冲突与空 `artifacts/` 边界；
- [ ] 未获得 reward 1，因此不标记为 `agent-validated`。

