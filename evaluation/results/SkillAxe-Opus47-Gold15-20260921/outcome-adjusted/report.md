# F→P 任务全 TP：替代计分

现有 Gold 评分保留不变；本文件仅基于已完成结果离线重算，无模型调用、无任务重跑。

- F→P任务：诊断和修复均设TP=Gold defect数量、FP=FN=0；其他任务保留原Gold评分。
- F→P任务：全部Gold defect设为TP、FN=0；保留原诊断额外误报FP及修复有害额外改动FP，移除被覆盖的Gold修复失败FP；其他任务保持原分。
- 仍统计15题32个Gold defect；2个基础设施异常任务保留原内容评分，不将其视为执行FAIL或PASS。
- 离线事后替代计分，不是Gold裁判重新认定。通过不证明逐项诊断正确或全部缺陷均被修复。定位、回归、置信度指标不重新推断。

6个F→P任务覆盖12个Gold defect。诊断TP由原来的3个覆盖为12个，净增9个；修复TP由1个覆盖为12个，净增11个。

## 汇总（micro）

| 口径 | 指标 | TP | FP | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| 原Gold评分 | 诊断 | 8 | 34 | 24 | 19.05% | 25.00% | 21.62% |
| 原Gold评分 | 修复 | 1 | 23 | 31 | 4.17% | 3.12% | 3.57% |
| 新版：通过任务整体满分 | 诊断 | 17 | 18 | 15 | 48.57% | 53.12% | 50.75% |
| 新版：通过任务整体满分 | 修复 | 12 | 14 | 20 | 46.15% | 37.50% | 41.38% |
| 附加：保留额外FP | 诊断 | 17 | 34 | 15 | 33.33% | 53.12% | 40.96% |
| 附加：保留额外FP | 修复 | 12 | 15 | 20 | 44.44% | 37.50% | 40.68% |

## 逐题核对

计数均为TP/FP/FN。INFRA_ERROR仅表示执行无有效结论，内容评分仍在15题汇总内。

| 任务 | 验证 | Gold缺陷数 | 原诊断 | 新诊断 | 原修复 | 新修复 |
|---|---|---:|---|---|---|---|
| azure-bgp-oscillation-route-leak | PASS | 1 | 1/2/0 | 1/0/0 | 0/1/1 | 1/0/0 |
| data-to-d3 | PASS | 1 | 0/3/1 | 1/0/0 | 0/1/1 | 1/0/0 |
| dynamic-object-aware-egomotion | FAIL | 3 | 1/2/2 | 1/2/2 | 0/2/3 | 0/2/3 |
| enterprise-information-search | FAIL | 1 | 0/4/1 | 0/4/1 | 0/3/1 | 0/3/1 |
| fix-build-agentops | FAIL | 2 | 1/2/1 | 1/2/1 | 0/2/2 | 0/2/2 |
| flink-query | PASS | 2 | 0/3/2 | 2/0/0 | 1/1/1 | 2/0/0 |
| jpg-ocr-stat | INFRA_ERROR | 1 | 1/2/0 | 1/2/0 | 0/1/1 | 0/1/1 |
| manufacturing-equipment-maintenance | FAIL | 2 | 0/1/2 | 0/1/2 | 0/0/2 | 0/0/2 |
| paper-anonymizer | PASS | 3 | 1/2/2 | 3/0/0 | 0/1/3 | 3/0/0 |
| pddl-airport-planning | PASS | 1 | 1/2/0 | 1/0/0 | 0/1/1 | 1/0/0 |
| python-scala-translation | FAIL | 3 | 0/4/3 | 0/4/3 | 0/1/3 | 0/1/3 |
| reserves-at-risk-calc | FAIL | 2 | 1/0/1 | 1/0/1 | 0/1/2 | 0/1/2 |
| seismic-phase-picking | PASS | 4 | 0/4/4 | 4/0/0 | 0/4/4 | 4/0/0 |
| shock-analysis-supply | INFRA_ERROR | 3 | 1/1/2 | 1/1/2 | 0/2/3 | 0/2/3 |
| video-silence-remover | FAIL | 3 | 0/2/3 | 0/2/3 | 0/2/3 | 0/2/3 |

数据来源：`../gold-evaluation/details.json`、`../gold-evaluation/summary.json`、`../manifest.json`、各任务真实`benchmark_result.json`。

`scores.json`包含两种替代口径的逐题明细与源结果路径。运行`python recalculate.py`可离线复算。
