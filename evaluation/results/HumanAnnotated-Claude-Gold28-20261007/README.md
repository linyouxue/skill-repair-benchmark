# Human-annotated Claude Gold28 repair evidence

截至2026-10-07，Claude Opus 4.7 人工标注结果为 **28个Gold任务、29组RI/D标注**：2026-10-02已完成的15题保持不变，本次新增13题验收通过。原始Claude FAIL选择集共29题，其中制造排程题单列为任务/检查器契约冲突，未计入Gold或PASS。

本目录由 `HumanAnnotated-Claude-Gold15-20261002` 改名并扩展而来。它是人工核查、AI协助整理的参考标注集，包含Skill修补及已有指导的执行强化；不能把所有原失败都归为Skill缺陷，也不能将通过解释为Skill修改的唯一因果证据。所有原始归因、已有指导、修补类别及限制保留在Gold与逐题audit中。

## 数量和验收口径

| 批次 | Gold任务 | 验收类别 |
| --- | ---: | --- |
| 原15题，2026-10-02 | 15 | 12 fresh-pass + 3 verifier-only-pass；本次未重跑 |
| 本次14题选择集，2026-10-06至07 | 13 | 12 fresh-pass + 1 verifier-revised-pass；另1题排除 |
| 合计 | **28** | **24 fresh-pass + 3 verifier-only-pass + 1 verifier-revised-pass** |

`paratransit-routing` 有两条修补记录，其余各一条，因此28个任务对应29组 `RI-*` / `D*`，两份Gold及submission一一对应。制造题不在Gold、submission或28行STATUS中，另见 [EXCLUSIONS.csv](EXCLUSIONS.csv)。

- **fresh-pass**：实际Agent交付经记录的原checker验收通过；不保证正常end_turn、所有字面要求均已执行或全部更广泛语义已证明。
- **verifier-only-pass**：原15题中的 `fix-build-agentops`、`reserves-at-risk-calc`、`azure-bgp-oscillation-route-leak`，保留原模型执行记录，另存真实交付的补验/契约证据；本次不新增模型执行。
- **verifier-revised-pass**：仅 `latex-formula-extraction`。原checker结果仍是有效FAIL，不能将其写成原checker PASS，或与未修订口径直接等同。

## 本次新增13题

以下测试与reward取自逐题验收记录。迭代数为实际parent iteration；本次预算上限为60。显式Skill调用数与正文预加载分别记录：0次显式调用并不表示正文未暴露。

| 任务 | 最终独立rollout后缀 | 验收 | 迭代 / 结束方式 | 显式Skill调用 | 证据 |
| --- | --- | --- | --- | ---: | --- |
| [adaptive-cruise-control](tasks/adaptive-cruise-control/annotation.md) | `round-1-r001` | 12/12，reward1 | 24 / end_turn | 0 | [audit](tasks/adaptive-cruise-control/round-1-r001-pass-audit.json) |
| [debug-trl-grpo](tasks/debug-trl-grpo/annotation.md) | `round-2-r001` | 12/12，reward1 | 22 / end_turn | 0 | [audit](tasks/debug-trl-grpo/round-2-r001-pass-audit.json) |
| [energy-ac-optimal-power-flow](tasks/energy-ac-optimal-power-flow/annotation.md) | `round-2-r001` | 23/24，1 skipped，reward1 | 11 / end_turn | 0 | [audit](tasks/energy-ac-optimal-power-flow/round-2-r001-pass-audit.json) |
| [fix-visual-stability](tasks/fix-visual-stability/annotation.md) | `round-3-r001` | 6/6，reward1 | 60 / max_iterations；无最终回复 | 0 | [audit](tasks/fix-visual-stability/round-3-r001-pass-audit.json) |
| [hvac-control](tasks/hvac-control/annotation.md) | `round-1-r001` | 7/7，reward1 | 22 / end_turn | 0 | [audit](tasks/hvac-control/round-1-r001-pass-audit.json) |
| [latex-formula-extraction](tasks/latex-formula-extraction/annotation.md) | `round-1-r001-recovery002` | 原6/7、reward0；v2 7/7、reward1 | 34 / end_turn | 0 | [audit](tasks/latex-formula-extraction/round-1-r001-recovery002-pass-revision-audit.json) |
| [paratransit-routing](tasks/paratransit-routing/annotation.md) | `round-2-r001` | 7/7，reward1 | 29 / end_turn | 0 | [audit](tasks/paratransit-routing/round-2-r001-pass-audit.json) |
| [pptx-reference-formatting](tasks/pptx-reference-formatting/annotation.md) | `round-2-r001-recovery002` | 12/12，reward1 | 35 / end_turn | 0 | [audit](tasks/pptx-reference-formatting/round-2-r001-recovery002-pass-audit.json) |
| [r2r-mpc-control](tasks/r2r-mpc-control/annotation.md) | `round-1-r001` | 6/6，reward1 | 14 / end_turn | 0 | [audit](tasks/r2r-mpc-control/round-1-r001-pass-audit.json) |
| [suricata-custom-exfil](tasks/suricata-custom-exfil/annotation.md) | `round-1-r001-recovery002` | 12/12，reward1 | 14 / end_turn | 0 | [audit](tasks/suricata-custom-exfil/round-1-r001-recovery002-pass-audit.json) |
| [threejs-to-obj](tasks/threejs-to-obj/annotation.md) | `round-1-r001` | 3/3，reward1 | 9 / end_turn | 0 | [audit](tasks/threejs-to-obj/round-1-r001-pass-audit.json) |
| [tictoc-unnecessary-abort-detection](tasks/tictoc-unnecessary-abort-detection/annotation.md) | `round-2-r001` | 3/3格式检查；semantic reward1 | 19 / end_turn | 1 | [audit](tasks/tictoc-unnecessary-abort-detection/round-2-r001-pass-audit.json) |
| [travel-planning](tasks/travel-planning/annotation.md) | `round-1-r001` | 10/10，reward1 | 19 / end_turn | 0 | [audit](tasks/travel-planning/round-1-r001-pass-audit.json) |

需要保留的具体边界：

- **能流题**：23项通过、1项因公开输入没有支路电流限制而跳过，并非24项全部执行通过。
- **视觉稳定题**：真实产物经原checker 6/6、reward1；Agent用完60次预算，没有正常最终回复，且audit保留未遵循的字面要求。
- **HVAC / R2R**：原checker通过，但模型自报指标的定义/采样时间与原口径存在差异；通过不能证明所有自报指标语义正确。
- **PPTX / Threejs**：保存了实际交付并核实XML/公开几何；没有据此声称完成视觉渲染、真实Blender导入或所有材质/法线语义验证。
- **Paratransit**：保存了实际可行路线与独立公开验证；模型自报需求比例和硬上界未被证明。
- **TicToc**：按用户确认固定日志中的candidate时间；保留Round1聚合错误的正常FAIL，Round2原checker格式3/3与独立semantic reward1。没有重新选择candidate，也没有继承GPT的通过或目标ID。

## LaTeX：独立的verifier修订

最终真实交付在原checker下仍为 **6/7、reward0**，原 `benchmark_result.json`、`result.json` 和reward未覆盖。同一份未修改交付在单独记录的 **verifier-revision-v2** 下为 **7/7、reward1**；补验没有新增模型调用。

v2修订来源括号笔误的普通加减分组修复边界，并修正RGBA像素差比较中的RGB假阳性。保留原式像素一致性、其余数学token与另六项检查；真实旧失败输出仍5/7，改动运算符的负控6/7，漏保留原式的负控5/7。被负控发现问题的v1未入Gold。

见 [完整验收audit](tasks/latex-formula-extraction/round-1-r001-recovery002-pass-revision-audit.json) 与 [修订差异/负控收据](tasks/latex-formula-extraction/repaired_run/validation_evidence/verifier-revision-v2/)。发布的是通用checker差异及收据，未发布包含隐藏oracle字面量的完整checker。原断言FAIL保留，修订口径不算新增Skill缺陷。

## 排除题：manufacturing-fjsp-optimization

公开policy冻结machine/start/end，而被冻结工序与硬停机窗口重叠；同时满足字面冻结和零停机重叠不可行。原checker未实际执行 `lock_fields` 约束，使freeze检查可能空通过。

用户已确认将其单列为 **task/verifier contract conflict**，排除纯Skill F→P修复。本次没有修改freeze/task/checker，没有新模型尝试，没有复现或接受false PASS；原Claude失败及GPT历史Gold保持不变。用户提供的GPT通过材料属于用户报告，本流程没有独立重读并核实GPT原轨迹。

见 [制造题annotation](tasks/manufacturing-fjsp-optimization/annotation.md)、[原审计](tasks/manufacturing-fjsp-optimization/original-audit.json)、[用户决策](campaign/user-decision-two-tasks-20261007.json)。

## 文件与阅读顺序

```text
HumanAnnotated-Claude-Gold28-20261007/
├── README.md / MANIFEST.json / STATUS.csv / EXCLUSIONS.csv
├── gold_repairs.json        # 人工RI记录，包含归因、修补、验收和限制
├── gold.json                # evaluation格式D记录，29组RI/D一一对应
├── submission.json          # 28题diagnoses与最终repaired_bundle
├── EVIDENCE_INDEX.json      # GitHub目录内可解析的证据路径
├── PUBLICATION.json / FILES.json  # 来源对应、逐文件大小/SHA256
├── campaign/                # 最终report、scope/state、完成收据与用户决策
├── tasks/<task-id>/
│   ├── annotation.md / repair_manifest.json / *audit.json  # 新批次及排除题
│   ├── repair_plans/        # 已实际使用的轮次修补计划
│   ├── repaired_skill/      # 最终rollout的完整冻结Skill bundle
│   ├── repaired_run/        # 原始元数据、ACP、真实pre-verifier归档和验收证据
│   └── previous_attempts/   # 新批次现存失败/void记录，未改写为通过
└── trajectory_timelines/    # 仓库export_trajectory.py生成的可读轨迹和索引
```

先读本README与 [STATUS.csv](STATUS.csv)，再通过 [EVIDENCE_INDEX.json](EVIDENCE_INDEX.json) 打开逐题annotation、选定rollout和audit。`gold.json` / `gold_repairs.json` 与本地最终主记录逐字节一致；其中历史本地source指针原样保留，GitHub可导航路径以EVIDENCE_INDEX为准。共享转换器没有修改。

原始模型运行仍在 [Opus47原Skill的79题发布集](../Opus47-OriginalSkill-79Tasks-20260920/README.md)。本目录保留新批次实际存在的失败/void证据，不把基础设施故障计为Skill失败，不通过verifier补验抹掉正常断言FAIL。只发布真实现存文件，旧实物缺口保留；没有从轨迹重建文件冒充原导出。原15题selected bundle、执行文件与Gold记录保持不变，见 [原Gold15固定版本](https://github.com/linyouxue/skill-repair-benchmark/tree/f24be6b1e4a7f10d360188b3c78be6b9974c929e/evaluation/results/HumanAnnotated-Claude-Gold15-20261002)。

新13题保存原始pre-verifier归档及SHA，逐题audit已核实与真实容器交付一致。verifier仅发布实际交付/公开文件及name/status投影，排除expected/oracle文件和原断言消息。大体积LLM wire、results.jsonl、trainer重复轨迹、模型/运行时缓存和完整工作区不发布；ACP为实际执行记录，可读MD由仓库既有脚本生成。LaTeX原wire脱敏限制与各题正文暴露核查结论仍在audit中，不额外声称未保存wire的原字节一致性。

## 协议、费用与归因限制

本次新增批次模型为 `openrouter/anthropic/claude-opus-4.7`，采用统一BenchmarkExecutor；OpenHands CLI固定commit `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`，SDK/tools `1.28.1`。60次parent预算、32768输出上限、无额外effort，最多一次text-only continuation且共享预算。原15题沿用各自已记录历史协议，不通过改写历史元数据统一口径。

新批次最终选定13个rollout共有 **312次provider请求**；含真实失败尝试的新批次累计结束请求为 **572**。这两个数字都不是费用或付费次数，未知费用保留 `null`。原15题不计入这组新批次请求数。

验收过程中出现的依赖、CPU后端、代理/路由、运行时、容器gate和人工契约介入均分别记录，限制因果比较。偶然暴露的评分信息及用户附件中的GPT算法、评分policy标签、答案数量/ID已永久披露并隔离，没有写入候选、模型输入、gate或目标。该附件不随结果发布。

所有PASS只证明所记录的验收口径；模型对已有正确指导的遗漏、工具行为、任务契约与Skill正文边界分别归因。`sole_causality_established=false` 与缺失原始实物等限制不会因通过而删除。已归档任务资源按用户规则精确清理；物理磁盘回收未知，不作为实验效果指标。

`evaluation/data/skillsBench_claude` 仍是固定的历史15题evaluation版本，本次只修正其证据目录链接；本目录提供完整的28题结果。GPT Gold与01/02/03历史Gold未修改。
