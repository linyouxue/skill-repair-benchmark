# WML GPT-5.2 交付说明

22 条受控修复：9 通过，13 失败，均有可采用的执行评分证据。5 条位置提示、12 条单点待修、5 条多点待修齐全。

共享对照：18 通过，15 失败，33/33 有效。

5 题无提示原题记录已按分工复用。4 条历史执行未发现所列异常；dialogue-parser 原历史记录虽得 1 分，但末尾工具 JSON 文本化，已保留异常标注，并按用户许可用 Tatumass GPT‑5.2、相同冻结修后 Skill、60 次预算补充验证。补充验证正常通过，三份产物实际导出。它与原 Zenmux 记录分开保存，不伪称同端点重跑。

语义复核：5/22 条目标修复成立；11/12 条留一实验保留其他 Gold。此为已标注的 AI 辅助复核，不能称作独立人工签字。任务通过不代表 Skill 缺陷一定修好。

D3 verifier 只做了用户授权的 SVG 文本读取兼容修正，断言和奖励公式不变；修正版通过参考验收，位置提示修后运行奖励 1。D3 完整 Gold 的模型运行若失败，作为有效执行失败单独解释；参考解法通过证明环境可验收，但不能保证模型每次使用 Gold Skill 都成功。

原始尝试、异常记录和旧分数未覆盖；本轮新 attempt 路径在 evidence/ATTEMPT_PLAN.json 与 INFRASTRUCTURE_RETRY_PLAN.json。全部历史 raw attempts 仍位于 FINAL_DELIVERY_CHECK.json 列出的本机归档根目录。此交付目录包含选定执行及部分先前选定记录，不伪称已复制全部 raw attempts。

完整目录验证与限制见 reports/FINAL_DELIVERY_CHECK.json；官方模板见 reports/score_template.csv；官方 runner 的收集输出见 reports/official_collection.json；模型运行 Markdown 和自动索引见 trajectory_timelines/。

历史归档缺失的任务产物不从模型文字、评分 JSON 或 Gold 重建。此工作完成了分工清单的结果整理，不等同于此前更严格的“所有历史产物全部重新打开”条件已经满足。

当前检查：

- exact_22_official_trials: True
- 5_location_12_single_5_multiple: True
- all_22_execution_valid: True
- all_22_bundle_input_preload_checks: True
- official_template_22_rows: True
- target_and_gold_preservation_labels_present: True
- AI_review_attributed_honestly: True
- five_historical_unhinted_bundles_retained: True
- historical_unhinted_files_match_published_blobs: True
- five_tasks_have_clean_historical_or_authorized_supplement: True
- historical_dialogue_anomaly_preserved: True
- shared_controls_33_valid: True
- all_new_attempts_finished: True
- all_timeline_jsonl_parse: True
- all_rendered_timelines_exist: True
- D3_user_authorized_compatibility_only: True
- WML_two_stage_provenance_44_calls: True