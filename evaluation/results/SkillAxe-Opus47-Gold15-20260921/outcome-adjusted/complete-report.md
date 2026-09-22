# 完整指标对照

三列依次为原Gold评分、F→P任务TP覆盖且FP/FN清零、F→P的Gold缺陷全部计TP但保留额外FP。后两者均为离线替代统计，不是新的Gold裁判结果。

定位保留原location_correct判定，并按脚本公式使用各版本的诊断TP作为分母。新增9个TP没有额外定位得分，因此35.29%不表示定位行为变差。回归、疑似新缺陷、置信度和复核信息沿用独立的原内容判定，不随P/R计分覆盖。

| 指标 | 原Gold | TP覆盖、FP清零 | TP覆盖、保留额外FP | 定义/说明 |
|---|---:|---:|---:|---|
| 诊断 TP | 8 | 17 | 17 |  |
| 诊断 FP | 34 | 18 | 34 |  |
| 诊断 FN | 24 | 15 | 15 |  |
| 诊断 PRECISION | 19.05% | 48.57% | 33.33% |  |
| 诊断 RECALL | 25.00% | 53.13% | 53.13% |  |
| 诊断 F1 | 21.62% | 50.75% | 40.96% |  |
| 修复 TP | 1 | 12 | 12 |  |
| 修复 FP | 23 | 14 | 15 |  |
| 修复 FN | 31 | 20 | 20 |  |
| 修复 PRECISION | 4.17% | 46.15% | 44.44% |  |
| 修复 RECALL | 3.13% | 37.50% | 37.50% |  |
| 修复 F1 | 3.57% | 41.38% | 40.68% |  |
| diagnosis_task_count | 15 | 15 | 15 | 参与诊断汇总的任务数 |
| location_correct_count | 6 | 6 | 6 | 保留原Gold定位命中，不因通过而增加 |
| location_accuracy | 75.00% | 35.29% | 35.29% | 定位正确数/诊断TP；新版6/17，原版6/8 |
| failed_gold_repair_count | 19 | 11 | 11 | 尝试修复但未正确完成的Gold缺陷；新版移除通过任务的8项 |
| harmful_extra_repair_count | 4 | 3 | 4 | 有害或无依据的额外改动；整体覆盖口径移除通过任务的1项 |
| substantively_modified_bundles | 15 | 15 | 15 | 存在实质修改的bundle数，沿用内容判定 |
| regressed_bundles | 5 | 5 | 5 | 内容裁判判为引入新缺陷的bundle数，沿用原判 |
| regression_rate | 33.33% | 33.33% | 33.33% | 发生回归的bundle/实质修改bundle=5/15；不是执行P→F率 |
| regression_count | 7 | 7 | 7 | 回归新缺陷数量，沿用原判 |
| possible_new_defect_count | 5 | 5 | 5 | 额外改动中的疑似新缺陷数；与回归计数不直接相加 |
| task_count | 15 | 15 | 15 | 原评测记录；未重新调用裁判 |
| total_gold_defect_count | 32 | 32 | 32 | 原评测记录；未重新调用裁判 |
| evaluated_task_count | 15 | 15 | 15 | 原评测记录；未重新调用裁判 |
| evaluated_gold_defect_count | 32 | 32 | 32 | 原评测记录；未重新调用裁判 |
| scored_task_count | 15 | 15 | 15 | 原评测记录；未重新调用裁判 |
| skipped_original_pass_task_count | 0 | 0 | 0 | 原评测记录；未重新调用裁判 |
| skipped_gold_defect_count | 0 | 0 | 0 | 原评测记录；未重新调用裁判 |
| skipped_original_pass_rate | 0.00% | 0.00% | 0.00% | 原评测记录；未重新调用裁判 |
| confidence_task_count | 15 | 15 | 15 | 原评测记录；未重新调用裁判 |
| total_judgment_count | 124 | 124 | 124 | 原评测记录；未重新调用裁判 |
| low_confidence_count | 37 | 37 | 37 | 原评测记录；未重新调用裁判 |
| low_confidence_rate | 29.84% | 29.84% | 29.84% | 原评测记录；未重新调用裁判 |
| review_item_count | 42 | 42 | 42 | 原评测记录；未重新调用裁判 |
| blocking_review_count | 0 | 0 | 0 | 原评测记录；未重新调用裁判 |

## 执行与产物

| 项目 | 结果 |
|---|---|
| 修复生成、完整bundle、submission任务数 | 15 / 15 / 15 |
| F→P / F→F / 基础设施异常 | 6 / 7 / 2 |
| 有效执行通过率 | 6/13 = 46.15% |
| 全部计划任务中已证实通过占比 | 6/15 = 40.00%（2题结果未知） |
| 执行P→F回归率 | 不适用：本轮只有原始失败任务 |
| 实际skill工具调用 | 有效13题合计1次（flink-query）；13题均有正文暴露证据 |
| 基础设施异常任务 | jpg-ocr-stat、shock-analysis-supply；不计有效FAIL |

## 评测配置

| 字段 | 值 |
|---|---|
| method_id | skillaxe-opus47-gold15-20260921 |
| benchmark_version | manual-gold-defects-20260917-v25-claude-fail15 |
| judge_model | openai/gpt-5.5 |
| reasoning_effort | medium |
| max_output_tokens | 8192 |
| temperature | None |
| prompt_version | skill-diagnosis-repair-v2.1 |
| scoring_version | skill-diagnosis-repair-scoring-v1.1 |
| original_pass_policy | organizer_verified_skip |
| evaluation_scope | all_gold_tasks |
| mode | llm |
| maximum_judge_requests | 30 |
| confidence_threshold | 0.8 |
| confidence_policy | warn_only |
| regression_basis | content_judgment |
| status | complete |

SkillAxe诊断/修复与任务重跑使用Claude Opus 4.7；裁判为GPT-5.5 medium。原始轨迹复用。上表37个低置信项与5个疑似新缺陷项构成42个复核提示；阻塞项为0。

来源：原gold-evaluation/summary.json、details.json和outcome-adjusted/scores.json。每个数值均保留原始全精度；显示百分比采用四舍五入至两位小数。
