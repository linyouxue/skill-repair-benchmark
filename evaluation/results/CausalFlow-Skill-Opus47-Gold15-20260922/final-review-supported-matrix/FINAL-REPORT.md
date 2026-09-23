# CausalFlow→Skill 最终汇总（AgentOps 验收环境修订版）

全部worker已结束。15题、32 Gold缺陷均有内容裁判；执行验收为 3 PASS、12 FAIL、0 INFRA_ERROR。全部15题已获得有效PASS/FAIL；AgentOps使用明确修订的py38–py312验收矩阵，原六版本矩阵结果另行保留。

有效执行通过率 **3/15 = 20.00%**；全15题已证实通过占比 20.00%；有效验收覆盖 15/15题、32/32 Gold缺陷。内容裁判覆盖仍为15题32缺陷。

**15个完整bundle均与原Skill逐字节相同，提交诊断数和实际Skill修改数均为0。** 因此fresh通过不能归因于Skill内容修复；F→P全TP只是用户指定的替代统计，不能解释成裁判认定全部缺陷已诊断或修复。

| 指标 | 原Gold语义评分 | F→P全Gold缺陷TP、FP/FN清零 | 说明 |
|---|---:|---:|---|
| 诊断 TP | 0 | 5 |  |
| 诊断 FP | 0 | 0 |  |
| 诊断 FN | 32 | 27 |  |
| 诊断 PRECISION | N/A | 100.00% |  |
| 诊断 RECALL | 0.00% | 15.62% |  |
| 诊断 F1 | 0.00% | 27.03% |  |
| 修复 TP | 0 | 5 |  |
| 修复 FP | 0 | 0 |  |
| 修复 FN | 32 | 27 |  |
| 修复 PRECISION | N/A | 100.00% |  |
| 修复 RECALL | 0.00% | 15.62% |  |
| 修复 F1 | 0.00% | 27.03% |  |
| 定位命中数 | 0 | 0 | 独立内容判定保留 |
| Location accuracy | N/A | 0.00% | 原定位命中/对应版本诊断TP |
| 诊断评分任务数 | 15 | 15 | 独立内容判定保留 |
| 实质修改bundle数 | 0 | 0 | 独立内容判定保留 |
| 回归bundle数 | 0 | 0 | 独立内容判定保留 |
| 回归缺陷数 | 0 | 0 | 独立内容判定保留 |
| 内容回归率 | N/A | N/A | 独立内容判定保留 |
| 尝试但失败的Gold修复数 | 0 | 0 | 独立内容判定保留 |
| 有害额外修改数 | 0 | 0 | 独立内容判定保留 |
| 疑似新缺陷数 | 0 | 0 | 独立内容判定保留 |
| task_count | 15 | 15 |  |
| total_gold_defect_count | 32 | 32 |  |
| evaluated_task_count | 15 | 15 |  |
| evaluated_gold_defect_count | 32 | 32 |  |
| scored_task_count | 15 | 15 |  |
| skipped_original_pass_task_count | 0 | 0 |  |
| skipped_gold_defect_count | 0 | 0 |  |
| skipped_original_pass_rate | 0.00% | 0.00% |  |
| confidence_task_count | 15 | 15 |  |
| total_judgment_count | 47 | 47 |  |
| low_confidence_count | 0 | 0 |  |
| low_confidence_rate | 0.00% | 0.00% |  |
| review_item_count | 0 | 0 |  |
| blocking_review_count | 0 | 0 |  |
| 平均/最低置信度 | 0.9968 / 0.9900 | 0.9968 / 0.9900 |  |

N/A表示分母为0。原定位0/0，不写成0%或100%；替代定位保留原命中，分母变为替代TP。内容回归0/0，无实质修改所以不适用。执行P→F回归率也不适用：本组均为历史原始失败任务。FN仍代表未解决Gold缺陷；“尝试但失败的修复”计数0不等于修复成功。

| 任务 | 执行结果 | Gold D | 原诊断/修复 TP-FP-FN | 替代诊断/修复 TP-FP-FN | 原生Skill调用 | 备注 |
|---|---|---:|---|---|---:|---|
| azure-bgp-oscillation-route-leak | FAIL | 1 | 0/0/1 | 0/0/1 | 0 |  |
| data-to-d3 | PASS | 1 | 0/0/1 | 1/0/0 | 0 |  |
| dynamic-object-aware-egomotion | FAIL | 3 | 0/0/3 | 0/0/3 | 0 |  |
| enterprise-information-search | FAIL | 1 | 0/0/1 | 0/0/1 | 0 |  |
| fix-build-agentops | FAIL | 2 | 0/0/2 | 0/0/2 | 0 | 验收矩阵修订为py38–py312；五环境真实测试 |
| flink-query | PASS | 2 | 0/0/2 | 2/0/0 | 1 | r002；r001 Maven基础设施错误隔离；3项测试通过 |
| jpg-ocr-stat | FAIL | 1 | 0/0/1 | 0/0/1 | 0 |  |
| manufacturing-equipment-maintenance | PASS | 2 | 0/0/2 | 2/0/0 | 0 |  |
| paper-anonymizer | FAIL | 3 | 0/0/3 | 0/0/3 | 0 |  |
| pddl-airport-planning | FAIL | 1 | 0/0/1 | 0/0/1 | 0 |  |
| python-scala-translation | FAIL | 3 | 0/0/3 | 0/0/3 | 0 | 输入重建（同一汇总） |
| reserves-at-risk-calc | FAIL | 2 | 0/0/2 | 0/0/2 | 0 |  |
| seismic-phase-picking | FAIL | 4 | 0/0/4 | 0/0/4 | 0 |  |
| shock-analysis-supply | FAIL | 3 | 0/0/3 | 0/0/3 | 0 | 存在Playwright/Excel-only与harness能力不匹配限制 |
| video-silence-remover | FAIL | 3 | 0/0/3 | 0/0/3 | 0 |  |

## 执行、方法及产物

| 项目 | 核验结果 |
|---|---|
| 完整bundle / submission / Gold覆盖 | 15 / 15 / 15题32缺陷 |
| 原生 n_skill_invocations / 正文暴露 | 1次（flink-query）；15/15有正文注入证据 |
| 干预总数 / 因果步骤 / 候选命令修复 | 344 / 2 / 6 |
| CausalFlow行动修复成功任务 | 2（data-to-d3、seismic-phase-picking） |
| 单次Skill转写模型调用 | 2题；13题无causal steps，按适配代码原样导出，无转写模型调用 |
| Skill诊断 / 实际修改 | 0 / 0；2次转写也返回空诊断和空修改 |
| 原始轨迹重跑 / 本次新增Gold调用 | 0 / 0；30个既有两阶段裁判响应全部保留 |
| 方法关系 | 行动重放成功与Skill fresh rollout通过是不同结果；本实验是CausalFlow→Skill适配版 |

## 未完成有效验收及限制

- `fix-build-agentops`：用户要求修复已披露的基础设施/协议冲突后，验收矩阵从py37–py312修订为py38–py312；Python 3.7无法安装原固定LangChain依赖。五个受支持版本均执行真实原测试，源码、模型patch和断言未改。仅重跑verifier，无模型或Gold调用。不能把此结果称为原六版本协议的纯缓存修复；原报告保存在`../final-review/`。
- `shock-analysis-supply`：实际失败有折旧率数量级错误证据，但任务要求Playwright/Excel-only，基础工具harness不能完整匹配；不将其泛称为毫无环境限制的纯模型能力结论。
- `python-scala-translation`：使用经用户同意的误脱敏代码重建输入；原日志保留，不声称全部输入无损重放。
- `flink-query` r001已隔离。r002冻结Skill不变，实际workspace在verifier前导出；不是从文字轨迹重建。

## 配置、证据与复算

Opus方法/转写/fresh：`anthropic/claude-opus-4.7`，max_tokens=32768；temperature、reasoning effort、thinking字段均未显式传入，不能把服务端默认值写成确定数值。fresh预算JPG=65，其余60。
Gold：GPT-5.5 medium，max_output_tokens=8192，temperature省略，confidence阈值0.8/warn_only；内容回归判定。既有prompt v2.1响应离线由scoring v1.4复算；F→P覆盖单独存储，原Gold不修改。

- `final-metrics.json`：逐题、两版全指标、执行覆盖及原始证据路径。
- `complete-metrics.csv`：完整指标对照表。
- `gold-v1.4/`：原Gold响应离线复算，人工隔离结果以明确来源的executor覆盖副本接入。
- `../final-audit-a.json`、`../final-audit-b.json`、`../final-audit-flink-r002.json`：轨迹及verifier人工审计。
- `../final-execution-audit-overrides.json`：AgentOps隔离依据；runner原始结果保持不变。
- `../verifier-recovery-agentops-20260923/`：真实补丁恢复、原脚本与依赖冲突证据。
- `../recovery-history/20260923-flink-verifier-root-recovery/`：旧失败及方法/Gold未改证据。

复算：使用本机WSL Python运行 `build_final_report.py`。只读既有实验输入，输出本目录；不会调用模型、重跑实验或覆盖原Gold。


修订证据：`../verifier-recovery-agentops-supported-matrix-20260923/`；复算时运行 `build_final_report.py --supported-matrix`。
