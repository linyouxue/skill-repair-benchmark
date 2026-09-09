# Core-25 当前已整理的 Gold 子集

本目录发布 **Core-25 中当前已整理的 7 个任务、14 个缺陷**，不是完整的 25 任务 Gold。扩展集尚未发布。数据版本为 `core25-gold-defects-20260909-v1`，保留来源的 `converted-draft` 状态与已知标注边界。

每个原始 RI 对应一个 defect，不重新拆分、合并或改写。缺陷描述、修复要求、`source_repair_id` 和 `source_details` 全部保留原文；发布仅筛选任务、调整数据版本和文件引用。Original 与 reference bundle、任务 prompts 均逐字节复制并核对。

## 范围与参考版本

| Task | Defect 数 | Reference 版本 |
| --- | ---: | --- |
| dialogue-parser | 1 | round-1 |
| exoplanet-detection-period | 1 | round-1 |
| python-scala-translation | 3 | round-2 |
| sec-financial-report | 3 | round-1 |
| paratransit-routing | 2 | round-1 |
| software-dependency-audit | 1 | adherence-reinforcement/round-3 |
| video-silence-remover | 3 | adherence-reinforcement/round-2 |
| 合计 | 14 | 7 个任务 |

## 文件

| 文件 | 用途 |
| --- | --- |
| `gold.json` | 评测器使用的 defect Gold，包含任务上下文 |
| `gold_repairs.json` | 同一 7 任务的原始 RI 清单，字段与文字未改写 |
| `bundle_sources.json` | 相对文件引用、历史来源标识、参考版本和验证边界；不依赖作者机器路径 |
| `originals/<task_id>/skills/` | 完整 Original Skill bundle |
| `originals/<task_id>/prompts.json` | 对应的原始任务提示 |
| `references/<task_id>/skills/` | 已冻结的参考修复 bundle |
| `submission.template.json` | 参评方法填写的 7 任务提交模板 |
| `submission.gold-reference.json` | Gold 预测与 reference bundle 的一致性自测输入 |
| `submission.original-input-check.json` | 空诊断与 Original bundle 的输入检查，**仅供 dry-run** |

包内 Original 共 38 文件，reference 共 38 文件，任务 prompts 共 7 文件；这 83 个文件共 391,969 字节。本目录提供内容评测所需的 Skill 与上下文，不包含完整任务数据、verifier 或任务执行环境。

## 使用边界

**公开 Gold 供评分和核查，不应读取它来生成参评方法的诊断或修复。** 参评方法使用 Original 和规定的任务输入。组织者维护统一 Gold、执行协议和裁判参数；同学在自己的机器上运行方法及 executor，再用本目录 Gold 生成全部评测指标。

复制 `submission.template.json` 到方法自己的提交目录，填写 `method_id`、逐任务 `diagnoses`，并将完整修复后 Skill 放入 `tasks/<task_id>/skills/`。`benchmark_version` 必须与本版 Gold 相同。模板中的空目录引用尚待方法填充，不能直接作为完成的提交。

正常任务必须提供诊断数组和完整 Final。原始运行通过时，可按评测说明改为 `original_pass` 跳过行，仍须保留全部 7 个任务。使用 `--executor-runs-dir` 指向本地完整运行目录，脚本自动核验跳过证据并汇总 Verified Fix Rate；同学不需要手写结果清单、申请组织者核验或回传运行文件。空诊断数组本身不等于跳过。

`benchmark_result.json` 和 `executor_request.json` 由同学本地的 `BenchmarkExecutor` 自动生成，不是组织者需要另外提供的 Gold 材料。全部指标的运行命令和输出说明见 [本地评测流程](../../README.md#同学在本地完成全部评测)。完整任务数据、verifier 与执行环境仍按仓库的 executor 指南配置。

评测器选取本目录的 `gold.json`。`submission.original-input-check.json` 和 `submission.gold-reference.json` 的目录引用均已在包内配齐，可先使用 `--dry-run` 核查完整输入；真实 bundle 较大，可显式使用 `--max-input-chars 2000000`，不会裁剪文件。正式调用模型须按评测说明显式选择执行模式和模型。

`submission.gold-reference.json` 直接使用 Gold 描述与位置构造预测，只用于检查 Gold 与参考内容的一致性，不能作为一种参评方法的成绩。**参考内容被判定满足要求，不保证实际任务一定跑通；参考 bundle 也不承诺自动获得满分。** 历史执行验证与本评测的语义判定分别保留，不相互替代。

## 已知来源边界

- `paratransit-routing`：统一 RI 清单保留两项，但历史 `annotation.md` 将该任务标为 `no-Gold-repair`，视作 Agent 遵循强化诊断。此冲突尚未裁决，本次发布沿用统一清单；reference 保留 round-1 实际 bundle，不将它描述为已证明成功的标准修复。
- `exoplanet-detection-period`：参考修复有 verifier-only diagnostic replay 证据，不能描述为正式可比的 fresh rollout 通过。
- `sec-financial-report`：原始服务器 rollout 未完整镜像到本地。Original 来自官方任务资源，已有 digest 核对证据表明与历史标注一致；来源表保留该证据，不把本次复制当作新执行验证。
- `software-dependency-audit`：参考为 content-validated / agent-validated / verifier-pass，验证运行启用了 completion guard。选取含固定数据库不变量修复的 adherence-reinforcement/round-3；其 manifest 保留历史 `candidate-not-yet-validated` 状态，后续标注记有内容检查与 guard 复测支持。完整 bundle 也含此前的遵循强化，未被重新裁剪。
- `video-silence-remover`：保留三项 Gold 与 adherence-reinforcement/round-2 bundle；参考验证具有 adherence-assisted 边界。后续 terminal-result gate 不属于这三项 Gold，未纳入本版 reference。round-2 manifest 记录过未执行修复目录的失败，不能据此将所有参考修复统一表述为 canonical 通过。

完整逐任务备注见 `bundle_sources.json` 和 `gold.json` 的 `source_notes`。其中 run/round 标识用于说明历史来源，不是对本次发布进行了任务重跑的声明。若之后调整 Gold 标签或验收标准，应发布新数据版本并对所有方法统一重计。
