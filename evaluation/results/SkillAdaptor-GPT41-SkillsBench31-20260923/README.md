# SkillAdaptor / GPT-4.1：SkillsBench31 诊断修复实验（已完成，待发布）

<!-- EXECUTOR_PROGRESS -->
**最新真实执行状态：complete。有效31/31，通过3，尚缺0；详见 [EXECUTOR_PROGRESS.md](EXECUTOR_PROGRESS.md)。原内容评测章节描述冻结提案阶段。**
<!-- /EXECUTOR_PROGRESS -->

**方法诊断、修复提案、人工标注对比和端到端执行均已完成；31/31 个任务有效，3/31 通过（9.68%）。** 机器状态见 `STATUS.json`。本目录尚未上传 GitHub，发布前仍需复核。

本实验覆盖人工 Gold 的 31 个失败任务、57 个缺陷。公开失败轨迹来自 GPT-5.2，诊断修复和真实回放使用 GPT-4.1；没有同模型 GPT-4.1 Original-Skill 对照，因此通过率可以报告，但不能把变化因果归因于 skill 修复本身。统一配置记录见 `provenance/experiment_protocol.json`。输入为林同学上传的 GPT-5.2 Original-Skill 代表轨迹、原始 skill bundle 和任务说明；方法诊断修复使用 GPT-4.1，人工对比裁判也使用 GPT-4.1。模型角色不同，分别记录；这不是 GPT-5.2 全流程实验。

## 已完成的人工标注对比

使用冻结官方评测器生成的62条请求与官方评分函数，对比 `skillsbench87` 的人工标注。没有删减输入，没有调整裁判置信度。逐任务结果见 `evaluation/details.json`，原始判断见 `evaluation/judge_responses.json`。

| 指标 | 结果 |
|---|---:|
| Diagnosis precision | 32.26%（10/31） |
| Diagnosis recall | 17.54%（10/57） |
| Diagnosis F1 | 22.73% |
| Repair precision | 76.19%（16/21） |
| Repair recall | 28.07%（16/57） |
| Repair F1 | 41.03% |
| 匹配成功诊断的位置准确率 | 30.00%（3/10） |
| 内容判断 regression rate | 3.23%（1/31） |
| 端到端 Verified Fix Rate | 9.68%（3/31） |

Diagnosis TP/FP/FN=10/21/47；Repair TP/FP/FN=16/5/41。上述 repair 分数是缺陷层面的内容判断，不能替代真实任务 verifier 通过率。150项裁判判断有58项低置信度提示（38.67%），保留在 `evaluation/review_queue.json`，尚未人工复核；官方评分允许这些非阻塞提示继续计分。

## 方法范围与实现限制

本实验名称为 **SkillAdaptor proposal-stage adaptation**：使用上游 Localizer → Linker → Reviser/Generator，逐任务生成一份最终提案，再独立进行真实任务回放。没有运行上游 held-out Validator、adoption、fault-chain 重试或整体回滚，因此不声称完整复现 SkillAdaptor 的迭代算法。

方法输入不含人工 Gold；Gold 只进入之后的裁判评估。上游 Linker 在本适配器中以 `skill_matcher=None` 使用任务内前十个skill；每个任务输出一个提案和一条格式转换后的诊断。新增skill与修订skill均保留完整bundle。

上游固定提交的 `enrich_artifact_skill_data` 向24个最终提案插入了与任务无关的“Copy branch names, commit counts, and move constraints…”规则。该原句在93次API请求/响应中出现0次，属于上游确定性后处理。此处保留原始结果，不对提案做事后人工修改。完整源码证据、影响任务和复现边界见 `provenance/skilladaptor_fidelity_audit.md` 与 `metadata/method_fidelity_audit.json`。

## 时间与代价

方法调用以 `method/api_calls.jsonl` 的完整追加记录为准，共93次调用。历史session汇总只覆盖恢复执行后的90次调用，因此仅作为历史记录保留，不用于总数计算。每任务数据见 `metadata/proposal_tasks.csv` 和 `metadata/stage_timing_totals.json`。

| 方法阶段 | API次数 | API耗时合计/秒 | 阶段wall time合计/秒 | Total tokens |
|---|---:|---:|---:|---:|
| 诊断（Localizer+Linker） | 62 | 327.555 | 337.820 | 311,666 |
| 修复（Reviser/Generator） | 31 | 267.811 | 285.134 | 212,200 |
| 合计 | 93 | 595.366 | 622.954 | 523,866 |

方法prompt tokens为500,520，completion tokens为23,346。阶段wall time不等于跨恢复会话的日历时间；API时间不包含全部文件读写、限流等待与本地后处理。

| 裁判阶段 | API次数 | API耗时合计/秒 | Total tokens |
|---|---:|---:|---:|
| Diagnosis judge | 31 | 200.352 | 872,069 |
| Repair judge | 31 | 406.629 | 1,745,200 |
| 合计 | 62 | 606.981 | 2,617,269 |

裁判总wall time为607.185秒。方法和裁判合计155次API调用、3,141,135 tokens。**AIGC网关没有返回可审计的实际收费，实际货币成本未知，不填0。** 新一代真实executor的逐任务时间、token和供应商估算费用见 `executor/selected_task_costs.*`；实际网关账单仍未知。历史配置排查与废弃运行的开销单列，不并入有效任务结果。

有效 executor 合计：614 次 provider 请求，27,021.2 秒 wall time（约 7.51 小时），4,859.85 秒观测 API 时间，22,961,433 tokens（22,869,474 prompt + 91,959 completion），供应商估算费用 $29.641596；实际网关收费未知。方法和裁判开销不计入上述 executor 汇总。 另有 20 条废弃/预检运行单列：8,315.4 秒 wall time、214 次请求、7,961,018 个可观测 token、估算费用 $10.263636；其中部分旧轮次缺少完整usage，详见 `overhead/preflight_accounting.json`。

## 真实executor状态与废弃运行

旧executor请求未显式发送 `max_tokens`，公司网关使用默认1024，造成输出截断。旧配置下所有运行统一作废，包括表面上 `execution_ok=true` 或 `protocol_evidence_valid=true` 的记录；不从中挑选通过结果，也不将其记为方法修复失败。排除说明见 `executor/invalidated_protocol_generation.json`。

必须以统一的显式输出预算重新执行全部31个冻结bundle，固定模型、task source、协议和选择规则。每个任务采用新配置下第一条有效运行；基础设施失败单独保留并允许修复后重试，不能按照reward择优。

本包的 `executor/selection.json` 已记录 31 个经健康审计选定的有效运行。最终官方报告为 3/31 通过、覆盖率 31/31（100%），端到端 Verified Fix Rate 为 9.68%。每条选定运行的 `executor_request.json`、`config.json`、`result.json`、`benchmark_result.json`、轨迹和 verifier 证据均已导出；VFR 主分母遵循官方评测器，同时并列报告通过数/31 与通过数/有效运行数。

## 冻结来源与预处理

| 内容 | 固定版本 |
|---|---|
| SkillAdaptor | `b26d1ab5a798f07e53048b5ff509e8535e9fa228` |
| skill-repair-benchmark / evaluator | `4b5e642da6b9b184776b322f78d6e476ae28c943` |
| SkillsBench tasks v1.1 | `b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af` |
| Gold | `manual-gold-defects-20260917-v25` |
| Judge prompt / scoring | `skill-diagnosis-repair-v2.1` / `skill-diagnosis-repair-scoring-v1.4` |
| Executor protocol | `skillrepair-v1`，version2，统一 `max_tokens=16384` generation |

按代表运行README处理enterprise答案模板tokens数值、simpo verifier的rich依赖、organize文件扫描范围，并保留jpg-ocr-stat的65次调用预算例外。对 seismic 的 setuptools/pkg_resources、simpo 的 uv index resolver、AgentOps 的 Python PATH 做了仅限运行环境的最小补丁；原始与补丁hash、审计和重试原因见 `provenance/` 与 `notes/`。源码与补丁hash见 `provenance/`。enterprise的模板0与verifier要求正token数之间仍有语义差异，未擅自修改verifier。

发布bundle来自已校验的远端快照：31个目录、273个文件，文件集合和SHA256均与方法冻结输入加最终提案一致。远端最初多余的133个文件和6个不同原始文件已隔离修正；详细记录见 `metadata/bundle_*`。没有修改最终提案。

## 文件布局

- `submission.json`：冻结的官方提交格式，bundle路径均相对此目录。
- `tasks/<task_id>/skills/`：31个完整最终skill bundle，共273文件。
- `method/api_calls.jsonl`、`method/tasks/`：方法原始请求响应、诊断、归因、候选、阶段时间和输入指纹。
- `evaluation/`：官方内容对比报告、裁判原始判断、请求、时间、usage、review queue；其中请求含Gold，仅供评估审计，不作为方法输入。
- `metadata/`：逐任务CSV、完整调用统计、方法与bundle审计。
- `provenance/`：固定提交、输入hash、任务清单、预处理与方法说明。
- `reproduction/`：实际使用的adapter、评估wrapper、官方评测脚本和汇总脚本快照；需在SkillDiagBench项目布局中使用。
- `executor/`：执行状态、废弃generation说明，以及31个经健康审计选定运行的真实轨迹与verifier证据。
- `FILE_MANIFEST.json`：除自身外文件的SHA256和字节数；任何最终更新后须重新生成。

## 复算与上传

内容对比已经由冻结官方 `combine_judgments`、`evaluate_task`、`write_reports` 函数完成，函数与文件hash见 `evaluation/cached_scoring_metadata.json`。修复bundle和冻结submission内容应保持不变。当前文件包实验已完成；发布复核和 GitHub 写入仍待处理。

上传目标是 `linyouxue/skill-repair-benchmark` 的 `evaluation/results/SkillAdaptor-GPT41-SkillsBench31-20260923/`。GitHub写入凭据尚未配置；本任务阶段没有上传。完成新executor、更新STATUS和hash后，按 `UPLOAD.md` 的独立分支/PR步骤上传，不覆盖已有GPT52结果。凭据仅放环境或凭据管理器，结果包不包含appid/API key。
