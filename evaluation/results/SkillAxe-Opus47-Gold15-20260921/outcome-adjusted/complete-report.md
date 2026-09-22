# 完整指标对照

三列依次为原Gold评分、F→P任务TP覆盖且FP/FN清零、F→P的Gold缺陷全部计TP但保留额外FP。后两者均为离线替代统计，不是新的Gold裁判结果。

定位保留内容裁判location_correct判定，并使用各版本的诊断TP作为分母。覆盖增加的TP不会自动增加定位命中。回归、疑似新缺陷、置信度和复核信息沿用独立的内容判定，不随P/R计分覆盖。

| 指标 | 原Gold | TP覆盖、FP清零 | TP覆盖、保留额外FP | 定义/说明 |
|---|---:|---:|---:|---|
| 诊断 TP | 7 | 16 | 16 |  |
| 诊断 FP | 35 | 19 | 35 |  |
| 诊断 FN | 25 | 16 | 16 |  |
| 诊断 PRECISION | 16.67% | 45.71% | 31.37% |  |
| 诊断 RECALL | 21.88% | 50.00% | 50.00% |  |
| 诊断 F1 | 18.92% | 47.76% | 38.55% |  |
| 修复 TP | 1 | 12 | 12 |  |
| 修复 FP | 23 | 14 | 15 |  |
| 修复 FN | 31 | 20 | 20 |  |
| 修复 PRECISION | 4.17% | 46.15% | 44.44% |  |
| 修复 RECALL | 3.13% | 37.50% | 37.50% |  |
| 修复 F1 | 3.57% | 41.38% | 40.68% |  |
| diagnosis_task_count | 15 | 15 | 15 | 参与诊断汇总的任务数 |
| location_correct_count | 5 | 5 | 5 | 保留原Gold定位命中，不因通过而增加 |
| location_accuracy | 71.43% | 31.25% | 31.25% | 保留内容裁判定位命中数/本列诊断TP |
| failed_gold_repair_count | 19 | 11 | 11 | 尝试修复但未正确完成的Gold缺陷；覆盖口径移除通过任务的对应项 |
| harmful_extra_repair_count | 4 | 3 | 4 | 有害或无依据的额外改动；整体覆盖口径移除通过任务的对应项 |
| substantively_modified_bundles | 15 | 15 | 15 | 存在实质修改的bundle数，沿用内容判定 |
| regressed_bundles | 5 | 5 | 5 | 内容裁判判为引入新缺陷的bundle数，沿用原判 |
| regression_rate | 33.33% | 33.33% | 33.33% | 发生回归的bundle/实质修改bundle；不是执行P→F率 |
| regression_count | 7 | 7 | 7 | 回归新缺陷数量，沿用原判 |
| possible_new_defect_count | 5 | 5 | 5 | 额外改动中的疑似新缺陷数；与回归计数不直接相加 |
| task_count | 15 | 15 | 15 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| total_gold_defect_count | 32 | 32 | 32 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| evaluated_task_count | 15 | 15 | 15 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| evaluated_gold_defect_count | 32 | 32 | 32 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| scored_task_count | 15 | 15 | 15 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| skipped_original_pass_task_count | 0 | 0 | 0 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| skipped_gold_defect_count | 0 | 0 | 0 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| skipped_original_pass_rate | 0.00% | 0.00% | 0.00% | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| confidence_task_count | 15 | 15 | 15 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| total_judgment_count | 122 | 122 | 122 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| low_confidence_count | 37 | 37 | 37 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| low_confidence_rate | 30.33% | 30.33% | 30.33% | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| review_item_count | 42 | 42 | 42 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| blocking_review_count | 0 | 0 | 0 | 合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断 |
| verified_fix_rate | 40.00% | 40.00% | 40.00% | 新版评测器直接核验的执行指标；不随内容计分覆盖 |
| verified_fix_status | complete | complete | complete | 新版评测器直接核验的执行指标；不随内容计分覆盖 |
| verified_fix_eligible_task_count | 15 | 15 | 15 | 新版评测器直接核验的执行指标；不随内容计分覆盖 |
| verified_fix_valid_task_count | 15 | 15 | 15 | 新版评测器直接核验的执行指标；不随内容计分覆盖 |
| verified_fix_passed_task_count | 6 | 6 | 6 | 新版评测器直接核验的执行指标；不随内容计分覆盖 |
| verified_fix_failed_task_count | 9 | 9 | 9 | 新版评测器直接核验的执行指标；不随内容计分覆盖 |
| verified_fix_invalid_task_count | 0 | 0 | 0 | 新版评测器直接核验的执行指标；不随内容计分覆盖 |
| verified_fix_missing_task_count | 0 | 0 | 0 | 新版评测器直接核验的执行指标；不随内容计分覆盖 |
| verified_fix_coverage | 100.00% | 100.00% | 100.00% | 新版评测器直接核验的执行指标；不随内容计分覆盖 |

## 执行与产物

| 项目 | 结果 |
|---|---|
| 完整bundle / submission任务数 | 15 / 15 |
| F→P / F→F / 基础设施异常 | 6 / 9 / 0 |
| 有效执行通过率 | 6/15 = 40.00% |
| 全部计划任务中已证实通过占比 | 6/15 = 40.00% |
| 执行P→F回归率 | 不适用：本轮只有原始失败任务 |
| 实际skill工具调用 / 正文暴露任务数 | 1 / 15 |
| JPG补跑 | r002真实预算60，达到迭代上限；只恢复原XLSX的verifier，未再调用模型。后续jpg预算已改65，历史记录不改写。 |
| 裁判新增调用 | 仅jpg与shock：4个有效响应；另有1次入站429拒绝，成功响应未重复调用。 |

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
| scoring_version | skill-diagnosis-repair-scoring-v1.4 |
| original_pass_policy | organizer_verified_skip |
| evaluation_scope | all_gold_tasks |
| mode | supplied_judgments |
| maximum_judge_requests | 30 |
| confidence_threshold | 0.8 |
| confidence_policy | warn_only |
| regression_basis | content_judgment |
| status | complete |

SkillAxe诊断/修复与任务重跑使用Claude Opus 4.7；裁判为GPT-5.5 medium。原始轨迹、修复bundle与其他13题内容裁判均复用。

来源：gold-evaluation/summary.json、details.json和outcome-adjusted/scores.json；evaluation-provenance.json记录裁判复用。每个数值保留全精度；显示百分比四舍五入至两位小数。
