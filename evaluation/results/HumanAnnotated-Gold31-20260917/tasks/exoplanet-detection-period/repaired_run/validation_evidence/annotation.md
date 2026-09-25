# 人工诊断与 Skill 修复标注：`exoplanet-detection-period`

## 1. 基本信息

| 字段 | 内容 |
|---|---|
| 标注状态 | `closed / Gold-repair / agent-validated via verifier-only diagnostic replay` |
| 标注方式 | `human-verified-ai-assisted` |
| Base model | `openrouter/openai/gpt-5.2` |
| Agent / protocol | `OpenHands / benchmark-executor skillrepair-v1` |
| Original task digest | `sha256:67bb300e81cee8649477be83aae60b4e145d41c5547694ee93b9bd6a1d6e33b4` |
| Round 1 patched task digest | `sha256:2f6d6922a19d3a2f55aefffb5f717c16d97d202135b4382fe9590b17dcd4ffe2`（仅含已归档的 TUNA Debian mirror / APT retry 基础设施补丁） |
| Original Skill bundle digest | `sha256:dab316dc730df3306bcc69089abc74f6547f22ad2e22f5198161192249c3efa0` |
| Round 1 Skill bundle digest | `sha256:c2a32c3345100f16b1ff517631ea58b47b797570c4593175c4c7923981426a1b` |
| Original rollout | `exoplanet-detection-period-original-skill-r001` |
| Round 1 validation | `exoplanet-detection-period-round-1-r006` |
| Original 证据目录 | `manual_annotation_runs/exoplanet-detection-period/runs/manual-annotation/exoplanet-detection-period-original-skill-r001/` |
| Round 1 证据目录 | `manual_annotation_runs/exoplanet-detection-period/runs/manual-annotation/exoplanet-detection-period-round-1-r006/` |

## 2. 功能步骤

| Step ID | 功能步骤 | 预期输出或状态 | 相关官方 Skill |
|---|---|---|---|
| S1 | 读取 TESS light curve，并按 quality flag 和有限值过滤 | 只保留可分析的 time、flux、quality、flux uncertainty | `light-curve-preprocessing`、`exoplanet-workflows` |
| S2 | 去除异常值和恒星活动，同时保留短时 transit dip | detrended light curve 不再由恒星宽周期变化主导 | `light-curve-preprocessing`、`exoplanet-workflows` |
| S3 | 用 transit-sensitive period search 做全局候选搜索 | TLS/BLS 找到可能的行星周期，而不是恒星活动残余 | `transit-least-squares`、`box-least-squares` |
| S4 | 检查候选的 phase fold、duration、odd/even、alias 和跨预处理稳定性 | 排除宽周期残余、谐波和不自洽候选 | `exoplanet-workflows`、`transit-least-squares`、`box-least-squares` |
| S5 | 对可信候选做局部 refinement，并写入 `/root/period.txt` | 单个正数，最多 5 位小数，且通过官方 period 验证 | `transit-least-squares` |

## 3. Original-Skill rollout

| Rollout ID | 官方通过 | Reward | 执行证据 | 最早失败步骤 | Failure ID |
|---|---:|---:|---|---|---|
| `exoplanet-detection-period-original-skill-r001` | 否 | 0.0 | `execution_ok=true`；`comparable=true`；18/60 iterations；18 provider requests；17 completed tool calls；clean `end_turn` | S2 | F1 |

官方 verifier 共 4 项，文件存在、可解析为正数和小数格式 3 项通过；唯一失败项是周期值：
Agent 写入 `1.39825`，官方期望 `5.35699`，容差为 `±0.01`。本轮没有 API、网络、
容器、timeout、iteration-limit、verifier 或导出执行错误，因此属于有效、可比较的任务失败。

本轮费用为 `$0.4048408`，provider 记录 657,238 tokens；总耗时 1447.2 秒，其中 Agent
执行 1292.0 秒。`artifacts/` 为空，但轨迹明确记录了 `/root/period.txt` 的创建和内容，
verifier 也成功读取该文件；因此记为非阻塞的 `evidence-archive gap`，不影响结果归因。

`n_skill_invocations=0` 不表示模型没有看到 Skill。统一 executor 已在第一次 task prompt 前将
以下 5 份完整 `SKILL.md` 正文确定性写入 persistent `AgentContext`：

- `box-least-squares/SKILL.md`
- `exoplanet-workflows/SKILL.md`
- `light-curve-preprocessing/SKILL.md`
- `lomb-scargle-periodogram/SKILL.md`
- `transit-least-squares/SKILL.md`

expected/observed bundle digest、Skill 数量和 preload marker 全部一致，
`skill_exposure_verified=true`。

## 4. 失败模式与可归因性

| Failure ID | Step | 可观察问题与最早根因 | 根因标签 | 进入 Gold repair | 证据与边界 |
|---|---|---|---|---:|---|
| F1 | S2 | Agent 没有先执行官方 TLS Skill 已给出的参考预处理，而是把初次异常值阈值改为 `sigma=10`，使用 801、1201、1601、2001、3001 cadences 的 flatten 窗口，并在 flatten 后再用 `sigma=6`。这些窗口约为 1.11–4.17 天，未充分移除任务明确指出的强恒星活动，后续搜索始终被约 1.398/2.80 天的宽残余信号主导。 | `agent_did_not_follow`；subtype=`incorrect-preprocessing` | 是（adherence reinforcement） | 官方 `transit-least-squares` Skill 的 Basic Usage 已给出 `remove_outliers(sigma=3) → flatten() → 带 flux_err 的 TLS`；`exoplanet-workflows` 也规定初次 sigma=3、优先 TLS、检查 phase fold 和候选一致性。官方 oracle 使用同一参考流程并得到可评分答案。 |
| F2 | S3–S4 | Agent 在 TLS 候选没有被可靠验证后，转而把 BLS 的最高 power 当作最终依据；最优 duration 多次恰好命中自设搜索上界（0.25、0.35、0.45 天），这是模型可能在拟合宽恒星变化的明显边界警告，却未触发候选拒绝。 | `agent_did_not_follow`；subtype=`invalid-candidate-selection` | 是（adherence reinforcement） | 官方 Skill 已要求优先 TLS、检查 reasonable duration、phase-fold、odd/even 和多指标，不允许仅凭单一最高 power 下结论。 |
| F3 | S4 | Agent 算出 1.398 天候选的 odd/even depth 差约为 transit depth 的 12.7%，两次 BLS 统计脚本还分别因 tuple 运算和缺少 `transit_count` key 报错；另一次所谓 double-period TLS 检查返回了请求范围之外的 1.394978 天。Agent 没有拒绝这些不自洽证据，仍写入该候选。 | `agent_did_not_follow`；subtype=`failed-validation-gate` | 是（adherence reinforcement） | `exoplanet-workflows`、BLS 和 TLS Skill 已明确要求 odd/even、alias、phase-fold 与多指标验证；这里缺少的是执行遵循，不是领域步骤。 |
| F4 | 归档 | sandbox 内 `/root/period.txt` 已生成并被 verifier 读取，但 runner 的 `artifacts/` 为空。 | `evidence_archive_gap` | 否 | 轨迹保存写入命令和 `1.39825`，verifier 保存 3/4 明细；足以复核失败，但无法从 artifacts 独立重放原文件。 |

最早可干预错误是 S2 的预处理参数选择。S3–S4 的错误是在错误 detrended curve 上继续进行
候选选择和验证，属于下游放大。严格按内容缺陷归因，现有官方 Skill 已包含参考 pipeline 和拒绝
错误候选所需的验证步骤，因此证据仍不支持 `skill_missing_guidance`、`skill_incorrect_guidance`、
`skill_ambiguous_guidance` 或 `skill_conflict`。但根据后续人工标注裁决，本任务允许将这些原本分散的
要求改写为显式、不可跳过的执行门，并把它作为 `adherence-reinforcement Gold repair`；这不等于宣称
官方 Skill 缺少该领域知识。

## 5. Gold repair items

| Repair ID | 目标 | 修改类型 | 结构化修复要求 |
|---|---|---|---|
| GR1 | 把参考预处理、候选选择与验证从建议提升为不可跳过的提交门 | `adherence reinforcement / decision gate` | 必须先完成 `quality/non-finite filtering → remove_outliers(sigma=3) → default flatten() → TLS with flux_err`；自定义 sigma、window、duration、BLS 和 Lomb–Scargle 只能作为 sensitivity check；使用 cadence window 前必须换算物理时间；duration 命中边界、验证代码失败、half/double-period 不一致或 phase-fold/odd-even 不自洽时必须拒绝候选并继续诊断；仅当参考结果和完整验证共同支持同一候选时才能写最终答案。 |

Round 1 只修改 `exoplanet-workflows/SKILL.md`，新增 `Mandatory Baseline-First Transit Search Gate`；
其余 4 份官方 Skill 与原版一致。修复没有写入官方期望周期 `5.35699`、容差或任务专用答案。

## 6. 人工修复轮次

| Round / rollout | Bundle | 自动流水线状态 | 结果与证据边界 |
|---|---|---|---|
| Round 1 `r001–r005` | `round-1/bundle/skills` | `infrastructure-invalid` | 均未形成可用的 Gold-repair 验证；其中 r005 在模型启动前因 Debian APT 502 构建失败，0 provider requests、0 cost。 |
| Round 1 `r006` | 同一 bundle；digest `sha256:c2a32c3345100f16b1ff517631ea58b47b797570c4593175c4c7923981426a1b` | 原自动结果仍为 `non-comparable / infrastructure_error` | Agent 以 `end_turn` 正常完成 26/60 iterations，25 个 tool calls 全部 completed，真实写入 `/root/period.txt = 5.35892`；随后 Ubuntu WSL Docker bridge 在 verifier 前间歇性卡顿，轨迹发布命令 10 秒超时，自动 verifier 未启动。 |
| r006 frozen-output verifier-only replay | 未修改官方 verifier | `diagnostic replay` | 从原容器逐字节恢复 8-byte `period.txt` 后，在原容器执行官方 `test.sh`：4/4 passed，`reward.txt=1`，且 replay 期间 0 次模型调用。 |

原 `result.json` 不回写，仍保留 `execution_ok=false / comparable=false / reward=null`，不能冒充一条
自动流水线完整成功的正式 benchmark rollout。人工标注层面，本次冻结输出由真实 Agent 生成、官方
verifier 全通过，因此按后续单次验证裁决记为 `agent-validated via diagnostic replay`；如果论文统计
要求严格的自动 `comparable=true`，仍需在相同 TUNA 环境补丁下完整 fresh rerun 一次。

## 7. 最终标签

| 字段 | 内容 |
|---|---|
| Final status | `closed / Gold-repair / agent-validated via verifier-only diagnostic replay` |
| Attribution | 原失败仍是预处理与候选验证偏离已暴露流程的 `agent_did_not_follow`；Gold repair 属于人工裁决的 adherence reinforcement，不宣称新增领域知识 |
| Gold failure modes | `adherence failure`：参考 pipeline、边界警告和 validation gate 未被模型当作强制约束 |
| Gold repair requirements | GR1：mandatory baseline-first pipeline + candidate rejection/validation gate |
| Agent 执行类错误 | F1：incorrect preprocessing；F2：invalid candidate selection；F3：failed validation gate |
| Tool/environment 问题 | Original rollout 无；Round 1 r006 在 Agent 完成后发生 Ubuntu WSL Docker bridge 间歇性卡顿，导致自动 verifier 前收尾失败；另有任务级 TUNA mirror 补丁，正式比较时必须统一使用 |
| Task/verifier 问题 | 未发现；verifier 的标量答案与容差检查正常，但只提供最终结果、不能替代步骤诊断 |
| Skill exposure | Original 与 Round 1 均为 `explicit invocation=0; persistent full-body exposure verified=true; 5 skills`；r006 expected/observed Round 1 digest 一致 |
| Official result | Original：reward 0.0、3/4、`1.39825`；Round 1 r006 原自动结果 reward=null/non-comparable，冻结输出 verifier-only replay：reward 1、4/4、`5.35892` |
| Artifacts | r006 原始 8-byte 输出已从原容器逐字节恢复到 `recovered/root/period.txt`；CTRF、reward、完整轨迹和恢复 provenance 已归档；原自动结果未被篡改 |

## 8. 人工确认清单

- [x] 已核对 benchmark result、ACP/LLM trajectory、官方 task、Skill、oracle 和 verifier；
- [x] 已确认 Original-Skill rollout 有效、可比较，不是网络、超时、预算或基础设施失败；
- [x] 已确认 5 份 Skill 全文 persistent preload，不以 `n_skill_invocations=0` 误判暴露；
- [x] 已定位最早错误功能决策及其下游 verifier 后果；
- [x] 已区分 Agent 代码报错与工具环境故障；
- [x] 已按后续人工裁决把既有流程强化为显式 adherence-reinforcement Gold repair，并单列其与内容缺陷归因的边界；
- [x] 已核对 Round 1 只修改 `exoplanet-workflows/SKILL.md`，未注入 verifier 答案；
- [x] 已逐字节恢复 r006 目标文件，并保存官方 verifier 4/4、reward 1 与 replay provenance；
- [x] 已保留 r006 原始 non-comparable 结果，没有用诊断 replay 冒充正式自动成功；
- [ ] 人工标注者最终复核并签字。

